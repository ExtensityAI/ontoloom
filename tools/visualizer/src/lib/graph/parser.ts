import Graph from "graphology"
import type { Ontology, Class } from "./schema"
import type { EdgeAttributes, NodeAttributes } from "./types"
import { type HydraGraph } from "./types"

/**
 * Compute hierarchy depth for each class by traversing superclass chains.
 * For multiple inheritance, uses max depth from any parent path.
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
        if (!cls || cls.sub_class_of.length === 0) {
            levels.set(name, 0)
            return 0
        }

        // Use max depth from all parents for consistent layering
        const maxParentLevel = Math.max(
            ...cls.sub_class_of.map((parent) => getLevel(parent, new Set(visited)))
        )
        const level = maxParentLevel + 1
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

    const n = Object.entries(ontology.classes).length
    const bound = n * Math.log(n)

    const classLevels = computeClassLevels(ontology.classes)
    const maxLevel = Math.max(...classLevels.values(), 0)
    const order = Object.keys(ontology.classes).length

    // Add class nodes
    Object.entries(ontology.classes).forEach(([name, cls], i) => {
        const level = classLevels.get(name) ?? 0

        G.addNode(name, {
            label: name,
            level,
            inverseLevel: maxLevel - level,
            parents: [],
            children: new Set<string>(),
            edges: new Set<string>(),

            x: bound * (Math.random() - 0.5),
            y: bound * (Math.random() - 0.5),
        })
    })



    // Add hierarchy edges (subclass -> superclasses)
    Object.entries(ontology.classes)
        .filter(([, cls]) => cls.sub_class_of.length > 0)
        .forEach(([name, cls]) => {
            cls.sub_class_of.forEach((parent) => {
                const edgeKey = `${name}-is-a->${parent}`

                G.addDirectedEdgeWithKey(edgeKey, name, parent, {
                    type: "arrow",
                    tag: "hierarchy",
                    label: "isA",
                    size: 2,
                    weight: 5,
                    source: name,
                    target: parent,
                })

                // Update children set
                G.getNodeAttributes(parent).children.add(name)
            })
        })

    // Add object property edges (domain -> range)
    Object.entries(ontology.object_properties).forEach(([propName, prop]) => {
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

    // add parent chains to node attributes (all ancestors via BFS)
    Object.entries(ontology.classes).forEach(([name, cls]) => {
        const attrs = G.getNodeAttributes(name)
        const visited = new Set<string>()
        const queue = [...cls.sub_class_of]

        while (queue.length > 0) {
            const parent = queue.shift()!
            if (visited.has(parent)) continue
            visited.add(parent)
            attrs.parents.push(parent)

            const parentCls = ontology.classes[parent]
            if (parentCls) {
                queue.push(...parentCls.sub_class_of)
            }
        }
    })

    return G
}
