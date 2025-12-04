from ontology_hydra.ontology.agents.updater.tools.apply_ops import ApplyOpsToolArgs
from ontology_hydra.ontology.agents.updater.tools.finish import CompleteToolArgs
from ontology_hydra.ontology.agents.updater.tools.grep import GrepToolArgs

ToolArgs = ApplyOpsToolArgs | GrepToolArgs | CompleteToolArgs
