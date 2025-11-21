"""Utility functions for mutating ontology state. These should only be used within mutation operations as values are NOT validated!"""

from ontology_hydra.ontology.state.models import (
    Class,
    ClassName,
    DataProperty,
    ObjectProperty,
    OntologyState,
    PrimitiveDataType,
    vartuple,
)


def update_class(
    cls: Class,
    name: ClassName | None = None,
    parent: ClassName | None = None,
    description: str | None = None,
):
    return Class(
        name=name or cls.name,
        parent=parent or cls.parent,
        description=description or cls.description,
    )


def replace_ontology_state(
    state: OntologyState,
    classes: vartuple[Class] | None = None,
    object_properties: vartuple[ObjectProperty] | None = None,
    data_properties: vartuple[DataProperty] | None = None,
):
    return OntologyState(
        classes=classes or state.classes,
        object_properties=object_properties or state.object_properties,
        data_properties=data_properties or state.data_properties,
    )


def replace_object_property(
    prop: ObjectProperty,
    name: str | None = None,
    domain: vartuple[ClassName] | None = None,
    range: vartuple[ClassName] | None = None,
    description: str | None = None,
):
    return ObjectProperty(
        name=name or prop.name,
        domain=domain or prop.domain,
        range=range or prop.range,
        description=description or prop.description,
    )


def replace_data_property(
    prop: DataProperty,
    name: str | None = None,
    domain: vartuple[ClassName] | None = None,
    range: PrimitiveDataType | None = None,
    description: str | None = None,
):
    return DataProperty(
        name=name or prop.name,
        domain=domain or prop.domain,
        range=range or prop.range,
        description=description or prop.description,
    )
