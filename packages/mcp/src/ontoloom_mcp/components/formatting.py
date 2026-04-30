from ontoloom.ontology.canonical import truncate_hash
from ontoloom.ontology.extract import iter_axiom_entities
from ontoloom.ontology.models.literals import IRI, EntityType
from ontoloom.ontology.types import (
    AxiomSummary,
    EntityInfo,
    EntityMatch,
    EntitySummary,
    HashedAxiom,
    UpsertSelectionResult,
)

SELECT_PREVIEW = 5
SELECT_INLINE_MAX = 20


def walk_unique_iris(axiom):  # A global: we are missing a param type here
    """Ordered unique IRIs referenced by an axiom (single walk, dedup preserved)."""
    seen: set[str] = set()
    out: list[str] = []
    for iri, _role, _pos in iter_axiom_entities(axiom):  # A: ignored params can be _
        s = str(
            iri
        )  # A global: why return str(IRI)? no reason! use IRI wherever possible, is much easier to understand - if you get IRI and there is no reason to stringify, DON'T!
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


def collect_axiom_iris(axioms: list[HashedAxiom]):
    """Extract unique entity IRIs from a list of hashed axioms (insertion-ordered)."""
    # A: inconsistent with name of single axiom walk?
    seen: set[str] = set()
    out: list[str] = []
    for ha in axioms:
        for iri_str in walk_unique_iris(ha.axiom):
            if iri_str not in seen:
                seen.add(iri_str)
                out.append(iri_str)
    return out


def format_iri_with_label(iri: str, labels: dict[str, str | None]):
    # A: this function is horrible - why do we need it? why is this to be done like this? like, what is labels, and why do we need to check if labels contains iri here? seems like it should be somewhere else, and done differently
    label = labels.get(iri)
    return f'{iri} "{label}"' if label else iri


def format_roles(roles: set[EntityType]):
    # A: good func
    return ", ".join(sorted(str(r) for r in roles)) or "none"


def _format_axiom_line(
    ha: HashedAxiom,
    labels: dict[str, str | None],
    iris: list[str] | None = None,
):
    """Format a single axiom line with inline label hints. `iris` precomputed avoids re-walking."""
    line = f"[{truncate_hash(ha.hash)}] {ha.axiom}"  # A: truncate_hash could also accept HashedAxiom (is there any reason it does not? where is it called? or maybe accept str and HashedAxiom?)
    if not labels:
        return line
    # A: do not like that iris is optional and used if passed in - what could we do? same with labels, this seems bad? maybe have a custom type for this stuff as well? but we need to look deeply to figure out which one and all
    if iris is None:
        iris = walk_unique_iris(ha.axiom)
    hints = [f'{iri} "{labels[iri]}"' for iri in iris if labels.get(iri)]
    if hints:
        line += "  # " + ", ".join(hints)
    return line


def format_diff(
    entries: list[tuple[str, HashedAxiom]],
    summary: str,
    labels: dict[str, str | None] | None = None,
    iris_per_entry: list[list[str]] | None = None,
):
    lb = labels or {}
    if (
        iris_per_entry is None
    ):  # A: this is weird do not like it at all, need to reason through please
        iris_per_entry = [None] * len(entries)  # type: ignore[list-item]
    changes = "\n".join(
        f"{tag} {_format_axiom_line(ha, lb, iris)}"
        for (tag, ha), iris in zip(entries, iris_per_entry, strict=True)
    )
    return f"{summary}\n\n```diff\n{changes}\n```"


def format_axiom_listing(
    axioms: list[HashedAxiom],
    labels: dict[str, str | None] | None = None,
    iris_per_axiom: list[list[str]] | None = None,
):
    if not axioms:
        return ""
    lb = labels or {}  # A: very much duplicated code with above, do not like, reason please
    if iris_per_axiom is None:
        iris_per_axiom = [None] * len(axioms)  # type: ignore[list-item]
    return "\n".join(
        _format_axiom_line(ha, lb, iris) for ha, iris in zip(axioms, iris_per_axiom, strict=True)
    )


def format_entity_inspect(
    iri: IRI,
    info: EntityInfo,
    labels: dict[str, str | None] | None = None,
):
    lb = labels or {}
    header = format_iri_with_label(
        str(iri), lb
    )  # A global: again, passing labels not good like that, what could we do?
    lines = [f"{header} ({format_roles(info.roles)})", ""]

    if info.annotations:
        lines.append("Annotations:")
        lines.extend(f'  {ann.property}: "{ann.value}"' for ann in info.annotations)
        lines.append("")

    total = sum(info.axiom_counts.values())
    if total:
        lines.append(f"Axioms (asserted): {total}")
        for typ, count in info.axiom_counts.most_common():
            lines.append(f"  {count} {typ}")

    return "\n".join(lines).rstrip()


def format_entity_summary(summary: EntitySummary):
    # A: consider, should this be a func on EntitySummary? maybe, is pure, right?
    # A global: generally consider: which funcs to put on data types, which to keep free? I guess pure functions can in theory be on the data types, but please talk through with me, very important

    lines = [f"{summary.total} entities total"]
    for role, count in summary.by_role.most_common():
        lines.append(f"  {count} {role}")
    return "\n".join(lines)


def format_axiom_summary(summary: AxiomSummary):
    # A: see above func
    lines = [f"{summary.total} axioms total"]
    for typ, count in summary.by_type.most_common():
        lines.append(f"  {count} {typ}")
    return "\n".join(lines)


def format_selection_result(
    kind_label: str,
    select: str,
    upserted: UpsertSelectionResult,
    page_text: str,
):
    # A: see above, also what are all these params? I guess we are missing sth like Selection or sth type!!!! this is not good
    parts = [f"{upserted.cardinality} {kind_label} -> {select!r} (sel@{upserted.content_hash})."]
    if upserted.old_cardinality is not None:
        parts.append(f"Overwrote previous ({upserted.old_cardinality} items).")

    if upserted.cardinality <= SELECT_INLINE_MAX:
        parts.append("")
        parts.append(page_text)
    else:
        parts.append(f"Preview (first {SELECT_PREVIEW}):")
        parts.append("")
        parts.append(page_text)
        parts.append(
            f"\nUse `read_selection(name={select!r})` to browse all {upserted.cardinality} results."
        )

    return "\n".join(parts)


def format_entity_search_page(matches: list[EntityMatch], total: int, offset: int):
    # A: again, need a type for this - EntitySearchPage or sth, derived from SearchPage that contains like total and offset or sth, and then matches on EntitySearchPage and all!!
    end = offset + len(matches)
    lines = [f"Showing {offset + 1}-{end} of {total} entities:"]
    lines.append("")
    for m in matches:
        role_str = format_roles(m.roles)
        label = ""
        for ann in m.annotations:
            if (
                str(ann.property) == "rdfs:label"
            ):  # A global: rdfs:label is a constant, so let's make it a constant somewhere, sth like RDFS_LABEL = IRI(...) in this way we also get free validation in case we have typos and we can scrap the str(...) here.
                label = f' "{ann.value}"'
                break
        lines.append(f"  {m.iri} ({role_str}){label}")
        lines.extend(
            f'    {ann.property}: "{ann.value}"'
            for ann in m.annotations
            if str(ann.property) != "rdfs:label"
        )
    return "\n".join(lines)
