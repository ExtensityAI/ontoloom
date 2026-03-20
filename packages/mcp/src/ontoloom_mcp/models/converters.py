"""Convert MCP input models (StrIRI, list) to core ontology models (IRI, tuple)."""

from __future__ import annotations

from ontoloom.core.ontology.models import axioms as core_axioms
from ontoloom.core.ontology.models import expressions as core_expr
from ontoloom.core.ontology.models.literals import IRI

from ontoloom_mcp.models import axioms as mcp_axioms
from ontoloom_mcp.models import expressions as mcp_expr
from ontoloom_mcp.models.iri import StrIRI


def convert_iri(s: StrIRI):
    """Parse 'prefix:local_name' into a structured IRI."""
    prefix, local_name = s.split(":")
    return IRI(prefix=prefix, local_name=local_name)


def convert_class_expression(e: mcp_expr.ClassExpression):
    match e:
        case str():
            return core_expr.NamedClass(iri=convert_iri(e))

        case mcp_expr.NamedClass():
            return core_expr.NamedClass(iri=convert_iri(e.iri))

        case mcp_expr.ObjectSomeValuesFrom():
            return core_expr.ObjectSomeValuesFrom(
                property=convert_iri(e.property),
                filler=convert_class_expression(e.filler),
            )

        case mcp_expr.ObjectIntersectionOf():
            return core_expr.ObjectIntersectionOf(
                operands=tuple(convert_class_expression(op) for op in e.operands),
            )

        case mcp_expr.ObjectOneOf():
            return core_expr.ObjectOneOf(individual=convert_iri(e.individual))

        case mcp_expr.ObjectHasValue():
            return core_expr.ObjectHasValue(
                property=convert_iri(e.property),
                individual=convert_iri(e.individual),
            )

        case mcp_expr.ObjectHasSelf():
            return core_expr.ObjectHasSelf(property=convert_iri(e.property))

        case mcp_expr.DataSomeValuesFrom():
            return core_expr.DataSomeValuesFrom(
                property=convert_iri(e.property),
                range=e.range,
            )

        case mcp_expr.DataHasValue():
            return core_expr.DataHasValue(
                property=convert_iri(e.property),
                value=e.value,
            )


def convert_axiom(a: mcp_axioms.Axiom):
    match a:
        # Annotations
        case mcp_axioms.AnnotationAssertion():
            return core_axioms.AnnotationAssertion(
                property=convert_iri(a.property),
                subject=convert_iri(a.subject),
                value=a.value,
            )

        # TBox — Class axioms
        case mcp_axioms.SubClassOf():
            return core_axioms.SubClassOf(
                sub_class=convert_class_expression(a.sub_class),
                super_class=convert_class_expression(a.super_class),
            )

        case mcp_axioms.EquivalentClasses():
            return core_axioms.EquivalentClasses(
                expressions=tuple(convert_class_expression(e) for e in a.expressions),
            )

        case mcp_axioms.DisjointClasses():
            return core_axioms.DisjointClasses(
                expressions=tuple(convert_class_expression(e) for e in a.expressions),
            )

        # RBox — Object property axioms
        case mcp_axioms.SubObjectPropertyOf():
            return core_axioms.SubObjectPropertyOf(
                sub_property=convert_iri(a.sub_property),
                super_property=convert_iri(a.super_property),
            )

        case mcp_axioms.SubObjectPropertyOfChain():
            return core_axioms.SubObjectPropertyOfChain(
                chain=tuple(convert_iri(i) for i in a.chain),
                super_property=convert_iri(a.super_property),
            )

        case mcp_axioms.EquivalentObjectProperties():
            return core_axioms.EquivalentObjectProperties(
                properties=tuple(convert_iri(i) for i in a.properties),
            )

        case mcp_axioms.TransitiveObjectProperty():
            return core_axioms.TransitiveObjectProperty(
                property=convert_iri(a.property),
            )

        case mcp_axioms.ReflexiveObjectProperty():
            return core_axioms.ReflexiveObjectProperty(
                property=convert_iri(a.property),
            )

        case mcp_axioms.ObjectPropertyDomain():
            return core_axioms.ObjectPropertyDomain(
                property=convert_iri(a.property),
                domain=convert_class_expression(a.domain),
            )

        case mcp_axioms.ObjectPropertyRange():
            return core_axioms.ObjectPropertyRange(
                property=convert_iri(a.property),
                range=convert_class_expression(a.range),
            )

        # RBox — Data property axioms
        case mcp_axioms.SubDataPropertyOf():
            return core_axioms.SubDataPropertyOf(
                sub_property=convert_iri(a.sub_property),
                super_property=convert_iri(a.super_property),
            )

        case mcp_axioms.EquivalentDataProperties():
            return core_axioms.EquivalentDataProperties(
                properties=tuple(convert_iri(i) for i in a.properties),
            )

        case mcp_axioms.DataPropertyDomain():
            return core_axioms.DataPropertyDomain(
                property=convert_iri(a.property),
                domain=convert_class_expression(a.domain),
            )

        case mcp_axioms.DataPropertyRange():
            return core_axioms.DataPropertyRange(
                property=convert_iri(a.property),
                range=a.range,
            )

        case mcp_axioms.FunctionalDataProperty():
            return core_axioms.FunctionalDataProperty(
                property=convert_iri(a.property),
            )

        # HasKey
        case mcp_axioms.HasKey():
            return core_axioms.HasKey(
                class_expression=convert_class_expression(a.class_expression),
                object_properties=tuple(convert_iri(i) for i in a.object_properties),
                data_properties=tuple(convert_iri(i) for i in a.data_properties),
            )
