import tempfile
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from logging import getLogger
from pathlib import Path
from typing import Literal, cast

from ontology_hydra.cqs.comittee import Comittee, generate_comittee_for_domain
from ontology_hydra.cqs.question_generation import (
    Duplicates,
    Question,
    QuestionDeduplicator,
    Questions,
    generate_questions,
)
from ontology_hydra.cqs.scoping import generate_scope_document, merge_scope_documents
from ontology_hydra.ontology.generator import generate_ontology
from ontology_hydra.ontology.models import Ontology
from ontology_hydra.utils.cache import Cache, CacheKey, DirectoryCache

logger = getLogger("ontology-hydra.pipe")
# use standard logging module as ontopipe is a tool/library and we do not want to enforce a specific logging library on users


def _generate_comittee(domain: str, cache: Cache):
    ck: CacheKey = ("comittee.json",)
    if (json := cache.read(ck)) is not None:
        return Comittee.model_validate_json(json)

    comittee = generate_comittee_for_domain(domain)
    cache.write(ck, comittee.model_dump_json(indent=2))

    return comittee


def _generate_scope_documents_with_cache(domain: str, comittee: Comittee, cache: Cache, group_size):
    groups = comittee.divide_into_groups(group_size)
    documents = [""] * len(groups)

    def process_group(i_group):
        i, group = i_group
        ck: CacheKey = ("scopes", f"{i}.txt")

        if (cached_doc := cache.read(ck)) is not None:
            return i, cached_doc

        doc = generate_scope_document(domain, [m.persona for m in group])
        cache.write(ck, doc)

        return i, doc

    with ThreadPoolExecutor() as executor:
        results = executor.map(process_group, enumerate(groups))
        for i, doc in results:
            documents[i] = doc

    return cast("list[str]", documents)


def _merge_scope_documents_with_cache(domain: str, documents: list[str], cache: Cache):
    ck: CacheKey = ("scopes", "merged.txt")
    if (cached_scope := cache.read(ck)) is not None:
        return cached_scope

    merged_scope = merge_scope_documents(domain, documents)
    cache.write(ck, merged_scope)

    return merged_scope


def _generate_scope_with_cache(domain: str, comittee: Comittee, group_size: int, cache: Cache):
    ck: CacheKey = ("scopes", "merged.txt")

    # in case the merged scope exists, we can load it directly and skip everything else
    if (cached_scope := cache.read(ck)) is not None:
        return cached_scope

    documents = _generate_scope_documents_with_cache(domain, comittee, cache, group_size)

    return _merge_scope_documents_with_cache(domain, documents, cache)


def _sort_cqs(cqs: Iterable[str]):
    """Sorts CQs by length of the question, longest first."""
    return sorted(cqs, key=lambda x: len(x.split(" ")), reverse=True)


def _deduplicate_cqs(cqs: list[str], cache: Cache) -> list[str]:
    cqs = _sort_cqs(set(cqs))
    questions = Questions(items=[Question(index=i, text=q) for i, q in enumerate(cqs)])

    deduplicator = cast("QuestionDeduplicator", QuestionDeduplicator())
    res: Duplicates = deduplicator(input=questions)

    deduplicator.contract_perf_stats()

    # TODO write duplicates to cache file, but not only with indexes but actual questions!
    cache.write(("cqs", "duplicates.json"), res.model_dump_json(indent=2))

    # deduplicate CQs based on the duplicates found (1. take new questions and 2. add all non-duplicates)
    deduplicated_cqs = {d.question for d in res.duplicates}
    deduplicated_cqs.update(set(cqs) - {cqs[i] for d in res.duplicates for i in d.indexes})

    len_before = len(cqs)
    cqs = _sort_cqs(deduplicated_cqs)
    logger.debug("Deduplicated %d CQs to %d unique CQs", len_before, len(cqs))
    return cqs


def _generate_cqs_with_cache(
    domain: str,
    merged_scope: str,
    group_size: int,
    comittee: Comittee,
    cache: Cache,
):
    ck: CacheKey = ("cqs", "cqs_combined.txt")

    # in case all cqs were generated and combined, we can load them directly and skip everything else
    if (cached_cqs := cache.read(ck)) is not None:
        return cached_cqs.split("\n")

    groups = list(comittee.divide_into_groups(group_size))
    cqs = [""] * len(groups)

    def process_group(i_group):
        i, group = i_group
        group_ck: CacheKey = ("cqs", f"cqs_{i}.txt")
        if (cached_group_cqs := cache.read(group_ck)) is not None:
            return i, cached_group_cqs.split("\n")

        group_cqs = generate_questions(domain, group, merged_scope)
        cache.write(group_ck, "\n".join(group_cqs))

        return i, group_cqs

    with ThreadPoolExecutor() as executor:
        results = executor.map(process_group, enumerate(groups))
        for i, group_cqs in results:
            cqs[i] = group_cqs

    # flatten the list of lists
    cqs = [cq for gcq in cqs for cq in gcq]

    # deduplicate CQs
    cqs = _deduplicate_cqs(cqs, cache)

    cache.write(ck, "\n".join(cqs))

    return cqs


def _generate_ontology_with_cache(
    cqs: list[str],
    cache: Cache,
    cqs_per_batch: int = 4,
):
    ck: CacheKey = ("ontology.json",)

    if (cached_ontology := cache.read(ck)) is not None:
        return Ontology.model_validate_json(cached_ontology)

    logger.debug("Generating ontology from %d CQs", len(cqs))
    ontology = generate_ontology(cqs, cqs_per_batch=cqs_per_batch, cache=cache)
    cache.write(ck, ontology.model_dump_json(indent=2))

    return ontology


def ontopipe(
    domain: str,
    group_size: int = 4,
    cqs_per_batch: int = 4,
    cache: Cache | Literal["use_temp_dir"] = "use_temp_dir",
) -> Ontology:
    """Runs the ontology-hydra pipeline to generate an ontology for the given domain.

    Args:
        domain (str): The domain for which to generate the ontology.
        group_size (int): The number of committee members to group together for scope and cq generation. Defaults to 4.
        cqs_per_batch (int): The number of CQs to process in a single batch during ontology generation. Defaults to 4.
        cache (Cache | Literal["use_temp_dir"]): The cache instance or 'use_temp_dir' to create a new temporary directory for caching."""

    if cache == "use_temp_dir":
        # use temp path for caching
        cache = DirectoryCache(Path(tempfile.mkdtemp("ontopipe")))

    logger.debug("Generating ontology for domain: '%s'", domain)

    comittee = _generate_comittee(domain, cache)
    logger.debug(
        "Generated comittee for domain '%s' with %d members",
        domain,
        len(comittee.members),
    )

    scope = _generate_scope_with_cache(domain, comittee, group_size, cache)
    logger.debug("Generated scope for domain '%s' with %d words", domain, len(scope.split(" ")))

    cqs = _generate_cqs_with_cache(domain, scope, group_size, comittee, cache)
    logger.debug("Generated %d CQs for domain '%s'", len(cqs), domain)

    ontology = _generate_ontology_with_cache(cqs, cache, cqs_per_batch=cqs_per_batch)

    logger.debug(
        "Generated ontology for domain '%s' with %d classes and %d properties",
        domain,
        len(ontology.classes),
        len(ontology.properties),
    )
    return ontology
