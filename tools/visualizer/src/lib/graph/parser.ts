import Graph from "graphology"
import type { Ontology, Class } from "./schema"
import type { EdgeAttributes, NodeAttributes } from "./types"
import { type HydraGraph } from "./types"

/**
 * Compute hierarchy depth for each class by traversing superclass chain
 */
const computeClassLevels = (
    classes: Record<string, Class>,
): Map<string, number> => {
    const levels = new Map<string, number>()

    const getLevel = (name: string, visited = new Set<string>()): number => {
        if (levels.has(name)) return levels.get(name)!
        if (visited.has(name)) return 0 // cycle protection

        visited.add(name)
        const cls = classes[name]
        if (!cls?.superclass) {
            levels.set(name, 0)
            return 0
        }

        const parentLevel = getLevel(cls.superclass, visited)
        const level = parentLevel + 1
        levels.set(name, level)
        return level
    }

    Object.keys(classes).forEach((name) => getLevel(name))
    return levels
}

export const createOntologyGraph = (ontology: Ontology) => {
    const G: HydraGraph = new Graph<NodeAttributes, EdgeAttributes>({
        multi: true,
        type: "mixed",
    })

    const classLevels = computeClassLevels(ontology.classes)
    const maxLevel = Math.max(...classLevels.values(), 0)
    const order = Object.keys(ontology.classes).length

    // Add class nodes
    Object.entries(ontology.classes).forEach(([name, cls], i) => {
        const angle = (i / order) * Math.PI * 2
        const level = classLevels.get(name) ?? 0

        G.addNode(name, {
            label: name,
            level,
            inverseLevel: maxLevel - level,
            parents: [],
            children: new Set<string>(),
            edges: new Set<string>(),

            x: Math.cos(angle) * 100,
            y: Math.sin(angle) * 100,
        })
    })



    // Add hierarchy edges (subclass -> superclass)
    Object.entries(ontology.classes)
        .filter(([, cls]) => cls.superclass)
        .forEach(([name, cls]) => {
            const edgeKey = `${name}-is-a->${cls.superclass}`

            G.addDirectedEdgeWithKey(edgeKey, name, cls.superclass!, {
                type: "arrow",
                tag: "hierarchy",
                label: "isA",
                size: 2,
                weight: 5,
                source: name,
                target: cls.superclass!,
            })

            // Update children set
            G.getNodeAttributes(cls.superclass!).children.add(name)
        })

    // Add object property edges (domain -> range)
    Object.entries(ontology.objectProperties).forEach(([propName, prop]) => {
        prop.domain.forEach((domain) => {
            prop.range.forEach((range) => {
                const edgeKey = `${domain}-${propName}->${range}`

                G.addDirectedEdgeWithKey(edgeKey, domain, range, {
                    type: "line",
                    tag: "property",
                    label: propName,
                    size: 1,
                    weight: 1,
                    source: domain,
                    target: range,
                })
            })
        })
    })

    // add parent chains to node attributes
    Object.entries(ontology.classes).forEach(([name, cls]) => {
        const attrs = G.getNodeAttributes(name)
        let current = cls

        while (current.superclass) {
            attrs.parents.push(current.superclass)
            current = ontology.classes[current.superclass]
        }
    })

    return G
}
