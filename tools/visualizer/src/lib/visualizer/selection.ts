import type Graph from "graphology"
import type { NodeSelection, ViewState } from "./types"

export const emptySelection = (): NodeSelection => ({
    node: null,
    parents: new Set(),
    children: new Set(),
    connectedEdges: new Set(),
})

export const createSelection = (
    node: string | null,
    graph: Graph | null,
): NodeSelection => {
    if (!node || !graph) return emptySelection()

    const attrs = graph.getNodeAttributes(node)
    return {
        node,
        parents: attrs.parents as Set<string>,
        children: attrs.children as Set<string>,
        connectedEdges: attrs.edges as Set<string>,
    }
}

export const getActiveSelection = (viewState: ViewState): NodeSelection =>
    viewState.pinned.node ? viewState.pinned : viewState.hovered
