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

    // Add class nodes
    Object.entries(ontology.classes).forEach(([name, cls]) => {
        const level = classLevels.get(name) ?? 0
        G.addNode(name, {
            label: name,
            level,
            inverseLevel: maxLevel - level,
            parents: new Set<string>(),
            children: new Set<string>(),
            edges: new Set<string>(),
        } )
    })

    const addEdgeToNodes = (edgeKey: string, source: string, target: string) => {
        const sourceAttrs = G.getNodeAttributes(source) as NodeAttributes
        const targetAttrs = G.getNodeAttributes(target) as NodeAttributes

        // source -> target means: target is a parent of source, source is a child of target
        sourceAttrs.parents.add(target)
        sourceAttrs.edges.add(edgeKey)
        targetAttrs.children.add(source)
        targetAttrs.edges.add(edgeKey)
    }

    // Add hierarchy edges (subclass -> superclass)
    Object.entries(ontology.classes)
        .filter(([, cls]) => cls.superclass)
        .forEach(([name, cls]) => {
            const edgeKey = `${name}-is-a->${cls.superclass}`
            G.addDirectedEdgeWithKey(edgeKey, name, cls.superclass!, {
                type: "arrow",
                tag: "hierarchy",
                label: "is a",
                size: 2,
                weight: 3,
                source: name,
                target: cls.superclass!,
            })
            addEdgeToNodes(edgeKey, name, cls.superclass!)
        })

    // Add object property edges (domain -> range)
    Object.entries(ontology.objectProperties).forEach(([propName, prop]) => {
        prop.domain.forEach((domain) => {
            prop.range.forEach((range) => {
                // Skip if nodes don't exist
                if (!G.hasNode(domain) || !G.hasNode(range)) return

                const edgeKey = `${domain}-${propName}->${range}`
                G.addDirectedEdgeWithKey(edgeKey, domain, range, {
                    type: "line",
                    label: propName,
                    size: 1,
                    weight: 1,
                    source: domain,
                    target: range,
                })
                addEdgeToNodes(edgeKey, domain, range)
            })
        })
    })

    return G
}

/**
 * Initialize node positions in a circle layout before force simulation
 */
export const initializeNodePositions = (graph: Graph): void => {
    let i = 0
    const order = graph.order

    graph.forEachNode((node, attrs) => {
        const x = parseFloat(String(attrs.x ?? ""))
        const y = parseFloat(String(attrs.y ?? ""))
        const angle = (i++ / order) * Math.PI * 2

        graph.setNodeAttribute(
            node,
            "x",
            Number.isFinite(x) ? x : Math.cos(angle) * 100,
        )
        graph.setNodeAttribute(
            node,
            "y",
            Number.isFinite(y) ? y : Math.sin(angle) * 100,
        )
    })
}
