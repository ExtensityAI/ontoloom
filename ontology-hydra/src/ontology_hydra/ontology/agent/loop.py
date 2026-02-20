from pathlib import Path

from ontology_hydra.config import HydraConfig
from ontology_hydra.utils.cache import Cache


def run_agent_loop(
    config: HydraConfig,
    cache: Cache,
    intent: str,
    input_paths: list[Path],
    output_path: Path,
    max_steps: int = 1000,
):

    for i in range(max_steps):
        pass
