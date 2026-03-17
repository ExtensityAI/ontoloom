from ontoloom.core.ontology.models.base import FrozenModel
from ontoloom.core.ontology.models.iri import ClassIRI, DataPropertyIRI, ObjectPropertyIRI


class Entity(FrozenModel):
    pass


class Class(Entity):
    iri: ClassIRI


class ObjectProperty(Entity):
    iri: ObjectPropertyIRI


class DataProperty(Entity):
    iri: DataPropertyIRI
