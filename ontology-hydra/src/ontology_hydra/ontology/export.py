import networkx as nx

from ontology_hydra.ontology.models import Ontology


def _normalize_text(value: str | None) -> str:
    """Ensure GEXF attributes never receive None or empty strings."""
    return value if value not in (None, "") else "-"


def _format_characteristics(values: list[str] | None) -> str:
    """Join characteristic flags into a single string for GEXF export."""
    return ", ".join(values) if values else "-"


def ontology_to_networkx(ontology: Ontology) -> nx.MultiDiGraph:
    """Convert an Ontology instance to a NetworkX MultiDiGraph.

    Nodes represent ontology classes. Edges include:
    - ``is-a`` edges from subclass to superclass.
    - Object property edges from each domain class to each range class, labelled by the property
      name.
    """
    G = nx.MultiDiGraph()

    # add classes as nodes and encode hierarchy edges
    for cls in ontology.classes.values():
        description = _normalize_text(cls.description.description if cls.description else None)
        constraints = _normalize_text(cls.description.constraints if cls.description else None)

        G.add_node(
            cls.name,
            type="class",
            description=description,
            constraints=constraints,
        )

        if cls.superclass:
            G.add_edge(
                cls.name,
                cls.superclass,
                relation="is-a",
                type="hierarchy",
            )

    # add object property edges
    for prop in ontology.object_properties.values():
        prop_description = _normalize_text(
            prop.description.description if prop.description else None
        )
        prop_constraints = _normalize_text(
            prop.description.constraints if prop.description else None
        )

        for domain in prop.domain:
            for range_ in prop.range:
                G.add_edge(
                    domain,
                    range_,
                    label=prop.name,
                    relation=prop.name,
                    type="object_property",
                    characteristics=_format_characteristics(prop.characteristics),
                    description=prop_description,
                    constraints=prop_constraints,
                )

    return G


if __name__ == "__main__":
    with open("/Users/adrian/Desktop/Projects/ontology-hydra/test/out/ontology/final.json") as f:
        ontology = Ontology.model_validate_json(f.read())

    G = ontology_to_networkx(ontology)
    nx.write_gexf(G, "/Users/adrian/Desktop/Projects/ontology-hydra/test/out/ontology/final.gexf")
