import sys
from pathlib import Path

from loguru import logger


def _get_pretty_format(record):
    level = record["level"].name

    if level == "DEBUG":
        return (
            "<dim>{time:YYYY-MM-DD HH:mm:ss} |</dim> "
            "<level>{level:<4}</level> <dim>|</dim> "
            "{message:<40} "
            "<dim>({name}:{line})</dim>\n"  # add file and line number
        )

    if level in ("ERROR", "WARNING", "CRITICAL"):
        return (
            "<dim>{time:YYYY-MM-DD HH:mm:ss} |</dim> "
            "<level>{level:<4}</level> <dim>|</dim> "
            "<level>{message:<40}</level> "  # colorize message too for better viz
            "<dim>({name}:{line})</dim>\n{exception}"  # add exception info
        )

    # default format
    return (
        "<dim>{time:YYYY-MM-DD HH:mm:ss} |</dim> "
        "<level>{level:<4}</level> <dim>|</dim> "
        "{message:<40} "
        "<dim>({module})</dim>\n"
    )


def configure_logging(
    level: str = "INFO",
    log_file: Path | None = None,
):
    """Configure logging for the application.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_file: Optional path to write logs to file
    """

    # remove default sinks
    logger.remove()

    # add stderr logging
    logger.add(
        sys.stderr,
        format=_get_pretty_format,
        level=level,
        colorize=True,
    )

    # log to file
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        logger.add(
            log_file,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level:<8} | {name} | {message}",
            level=level,
        )

    logger.enable("ontology_hydra")
