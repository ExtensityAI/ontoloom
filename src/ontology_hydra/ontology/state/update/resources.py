from typing import Literal

from ontology_hydra.ontology.state.models import ClassName, Model, PropertyName

type ResourceKind = Literal["class", "data_property", "object_property", "any_property"]


class ResourceRef(Model):
    kind: ResourceKind
    name: ClassName | PropertyName
