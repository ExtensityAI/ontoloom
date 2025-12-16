from typing import Literal

from pydantic import BaseModel

from ontology_hydra.ontology.models import Class, DataProperty, ObjectProperty, Ontology


class ClassExport(BaseModel):
    data: Class

    parents: list[str]
    children: list[str]


class DataPropertyExport(BaseModel):
    type: Literal["data"] = "data"
    data: DataProperty


class ObjectPropertyExport(BaseModel):
    type: Literal["object"] = "object"
    data: ObjectProperty


class OntologyExport(BaseModel):
    classes: list[ClassExport]
    properties: list[DataPropertyExport | ObjectPropertyExport]


with open("/Users/adrian/Desktop/Projects/ontology-hydra/test/out/ontology/partial.json") as f:
    ontology = Ontology.model_validate_json(f.read())


export = OntologyExport(
    classes=[
        ClassExport(
            data=cls,
            parents=[parent.name for parent in ontology.get_ancestors(cls)],
            children=[child.name for child in ontology.get_descendants(cls)],
        )
        for cls in ontology.classes.values()
    ],
    properties=[
        DataPropertyExport(data=prop)
        if isinstance(prop, DataProperty)
        else ObjectPropertyExport(data=prop)
        for prop in ontology.properties.values()
    ],
)

with open("/Users/adrian/Desktop/Projects/ontology-hydra/test/out/ontology_export.json", "w") as f:
    f.write(export.model_dump_json(indent=2))

print(
    "Exported ontology to /Users/adrian/Desktop/Projects/ontology-hydra/test/out/ontology_export.json"
)
