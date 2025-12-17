import type { HydraGraph } from "../graph/types"
import type { NodeSelection } from "./types"

export const emptySelection = (): NodeSelection => ({
    node: null,
    parents: new Set(),
    children: new Set(),
    connectedEdges: new Set(),
})

export const createSelection = (
    node: string | null,
    graph: HydraGraph | null,
): NodeSelection => {
    if (!node || !graph || !graph.hasNode(node)) return emptySelection()

    const attrs = graph.getNodeAttributes(node)
    return {
        node,
        parents: attrs.parents,
        children: attrs.children,
        connectedEdges: attrs.edges,
    }
}
