import type { HydraGraph, NodeAttributes } from './types'

export interface NodeSelection {
    node: string
    attrs: NodeAttributes
    parents: ReadonlySet<string>
    children: ReadonlySet<string>
}

export const createSelection = (
    node: string,
    graph: HydraGraph,
): NodeSelection => {
    const attrs = graph.getNodeAttributes(node)

    return {
        node,
        attrs,
        parents: new Set(attrs.parents),
        children: attrs.children,
    }
}
