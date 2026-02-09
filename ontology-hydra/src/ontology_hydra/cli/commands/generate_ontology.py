from datetime import UTC, datetime

from loguru import logger
from tqdm import tqdm

from ontology_hydra.cli.args import GenerateOntologyArgs
from ontology_hydra.cli.components.title import generate_title
from ontology_hydra.config import load_config
from ontology_hydra.metrics import compute_iteration_metrics, compute_ontology_metrics
from ontology_hydra.ontology.components.implementation.pipeline import implement_plan
from ontology_hydra.ontology.components.planning.pipeline import generate_plan
from ontology_hydra.ontology.models import BASE_ONTOLOGY
from ontology_hydra.ontology.run import RunMetadata
from ontology_hydra.utils.cache import DirectoryCache


def generate_ontology(args: GenerateOntologyArgs):
    try:
        config = load_config(args.config_path)
    except ValueError as exc:
        msg = f"Invalid config file '{args.config_path}': {exc}"
        raise SystemExit(msg) from exc

    logger.info("Input files: {}", [str(p) for p in args.input_paths])

    run_dir = args.output_dir_path / args.id
    run_dir.mkdir()

    cache = DirectoryCache(run_dir)
    logger.info("Cache path: {}", cache.path)

    title = generate_title(config, args.intent)

    meta = RunMetadata(
        id=args.id,
        title=title,
        intent=args.intent,
        input_files=[p.name for p in args.input_paths],
        created_at=datetime.now(UTC),
        n_iterations=0,
    )

    cache.write("run.json", meta.model_dump_json(indent=4))

    ontology = BASE_ONTOLOGY

    for i in tqdm(range(50)):
        logger.info("Iteration {}/50", i + 1)

        old_ontology = ontology.clone()
        plan = generate_plan(config, args.intent, ontology)
        cache.write((i, "plan.md"), plan)

        ops, review, ontology = implement_plan(
            config, plan, args.intent, ontology, max_attempts=10
        )
        cache.write((i, "ops.json"), ops.model_dump_json(indent=4))
        cache.write(
            (i, "review.md"),
            f"{review.text}\n\n---\n\nVerdict: **{'ACCEPT' if review.accepted else 'REJECT'}**",
        )
        cache.write((i, "ontology.json"), ontology.model_dump_json(indent=2))
        ontology_metrics = compute_ontology_metrics(ontology)
        iteration_metrics = compute_iteration_metrics(ops.ops, old_ontology, ontology)
        cache.write(
            (i, "ontology_metrics.json"),
            ontology_metrics.model_dump_json(indent=2),
        )
        cache.write(
            (i, "iteration_metrics.json"),
            iteration_metrics.model_dump_json(indent=2),
        )

        logger.info(
            "Iteration {} complete: {} classes, {} properties",
            i + 1,
            len(ontology.classes),
            len(ontology.data_properties) + len(ontology.object_properties),
        )
        meta.n_iterations = i + 1
        cache.write("run.json", meta.model_dump_json(indent=4))
