import Graph from "graphology"
import type { OntologyExport, ClassExport } from "./schema"

const addClassNode = (G: Graph, clazz: ClassExport) => {
    return G.addNode(clazz.data.name, {
        label: clazz.data.name,
        size: 8 + (clazz.children.length)
    })
}

const addSuperclassEdge = (G: Graph, clazz: ClassExport) => {
    if (!clazz.data.superclass) {
        throw new Error(`Class ${clazz.data.name} has no superclass`)
    }

    return G.addDirectedEdgeWithKey(
        `${clazz.data.name}-is-a->${clazz.data.superclass}`,
        clazz.data.name,
        clazz.data.superclass,
        {
            type: "arrow",
            label: "is-a",
            size: 4
        },
    )
}

export const createGraph = (ontology: OntologyExport): Graph => {
    const G = new Graph({
        multi: true,
        type: "mixed",
    })

    // add class nodes
    ontology.classes.forEach((c) => addClassNode(G, c))

    // add edges from subclass to superclass
    ontology.classes
        .filter((cls) => cls.data.superclass)
        .forEach((cls) => addSuperclassEdge(G, cls))
        

    return G
}
