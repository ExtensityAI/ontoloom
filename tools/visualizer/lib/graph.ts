import Graph from "graphology"
import type { OntologyExport } from "./schema"

export const createOntologyGraph = (ontology: OntologyExport): Graph => {
    const G = new Graph({
        multi: true,
        type: "mixed",
    })

    const maxParentCount = Math.max(
        ...ontology.classes.map((c) => c.parents.length),
        1,
    )

    // add class nodes
    ontology.classes.forEach((c) =>
        G.addNode(c.data.name, {
            label: c.data.name,
            level: c.parents.length, // level based on depth in hierarchy
            inverseLevel: maxParentCount - c.parents.length,
        }),
    )

    // add edges from subclass to superclass
    ontology.classes
        .filter((cls) => cls.data.superclass)
        .forEach((cls) =>
            G.addDirectedEdgeWithKey(
                `${cls.data.name}-is-a->${cls.data.superclass}`,
                cls.data.name,
                cls.data.superclass,
                {
                    type: "arrow",
                    tag: "hierarchy",
                    label: "is a",
                    size: 2,
                    weight: 3,
                    source: cls.data.name,
                    target: cls.data.superclass,
                },
            ),
        )

    ontology.properties
        .filter((p) => p.type === "object")
        .forEach((prop) => {
            const domainClasses = prop.data.domain
            const rangeClasses = Array.isArray(prop.data.range)
                ? prop.data.range
                : [prop.data.range]

            domainClasses.forEach((domain) => {
                rangeClasses.forEach((range) => {
                    G.addDirectedEdgeWithKey(
                        `${domain}-${prop.data.name}->${range}`,
                        domain,
                        range,
                        {
                            type: "line",
                            label: prop.data.name,
                            size: 1,
                            weight: 1,
                            source: domain,
                            target: range,
                        },
                    )
                })
            })
        })

    return G
}
