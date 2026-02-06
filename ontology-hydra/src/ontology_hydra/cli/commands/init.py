from typing import TYPE_CHECKING

from loguru import logger

from ontology_hydra.config import init_config

if TYPE_CHECKING:
    from ontology_hydra.cli.args import InitArgs


def init(args: InitArgs):
    try:
        init_config(args.config_path)
    except (FileExistsError, FileNotFoundError) as exc:
        msg = str(exc)
        raise SystemExit(msg) from exc

    logger.info(f"Config template written to {args.config_path}")
