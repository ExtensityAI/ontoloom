from typing import cast

from symai.components import DynamicEngine

from ontology_hydra.config import ComponentName, HydraConfig


def create_component_engine(config: HydraConfig, name: ComponentName):
    """Returns a `symbolicai.DynamicEngine` for the given component, allowing different AI models for different components."""

    component = config.resolve_component(name)
    provider = config.providers[component.provider]

    return cast(
        "DynamicEngine", DynamicEngine(model=component.model, api_key=provider.api_key)
    )
