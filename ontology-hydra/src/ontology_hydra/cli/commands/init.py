from loguru import logger

from ontology_hydra.cli.args import InitArgs
from ontology_hydra.config import init_config


def init(args: InitArgs):
    try:
        init_config(args.config_path)
    except (FileExistsError, FileNotFoundError) as exc:
        msg = str(exc)
        raise SystemExit(msg) from exc

    logger.info("Config template written to {}", args.config_path)
