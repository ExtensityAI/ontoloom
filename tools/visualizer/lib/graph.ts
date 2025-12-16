import Graph from "graphology"
import type { OntologyExport } from "./schema"

export interface NodeAttributes {
    label: string
    level: number
    inverseLevel: number
    parents: Set<string>
    children: Set<string>
    edges: Set<string>
}

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
            level: c.parents.length,
            inverseLevel: maxParentCount - c.parents.length,
            parents: new Set<string>(),
            children: new Set<string>(),
            edges: new Set<string>(),
        } satisfies NodeAttributes),
    )

    const addEdgeToNodes = (edgeKey: string, source: string, target: string) => {
        const sourceAttrs = G.getNodeAttributes(source) as NodeAttributes
        const targetAttrs = G.getNodeAttributes(target) as NodeAttributes

        // source -> target means: target is a parent of source, source is a child of target
        sourceAttrs.parents.add(target)
        sourceAttrs.edges.add(edgeKey)
        targetAttrs.children.add(source)
        targetAttrs.edges.add(edgeKey)
    }

    // add edges from subclass to superclass
    ontology.classes
        .filter((cls) => cls.data.superclass)
        .forEach((cls) => {
            const edgeKey = `${cls.data.name}-is-a->${cls.data.superclass}`
            G.addDirectedEdgeWithKey(
                edgeKey,
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
            )
            addEdgeToNodes(edgeKey, cls.data.name, cls.data.superclass!)
        })

    ontology.properties
        .filter((p) => p.type === "object")
        .forEach((prop) => {
            const domainClasses = prop.data.domain
            const rangeClasses = Array.isArray(prop.data.range)
                ? prop.data.range
                : [prop.data.range]

            domainClasses.forEach((domain) => {
                rangeClasses.forEach((range) => {
                    const edgeKey = `${domain}-${prop.data.name}->${range}`
                    G.addDirectedEdgeWithKey(
                        edgeKey,
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
                    addEdgeToNodes(edgeKey, domain, range)
                })
            })
        })

    return G
}
