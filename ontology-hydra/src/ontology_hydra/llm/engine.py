from typing import TYPE_CHECKING, cast

from symai.components import DynamicEngine

if TYPE_CHECKING:
    from ontology_hydra.config import ComponentName, HydraConfig


def create_component_engine(config: HydraConfig, name: ComponentName):
    """Returns a `symbolicai.DynamicEngine` for the given component, allowing different AI models for different components."""

    component = config.resolve_component(name)
    provider = config.providers[component.provider]
    kwargs = component.kwargs or {}  # TODO: kwargs need to be passed to `the call of the engine!`

    return cast("DynamicEngine", DynamicEngine(model=component.model, api_key=provider.api_key))
