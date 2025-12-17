import type FA2Layout from "graphology-layout-forceatlas2/worker"
import type { HydraSigma, HydraGraph } from "../graph/types"

export interface NodeSelection {
    node: string | null
    parents: Set<string>
    children: Set<string>
    connectedEdges: Set<string>
}

export interface ViewState {
    hovered: NodeSelection
    pinned: NodeSelection
}

export interface RuntimeState {
    isLoading: boolean
    isLayoutRunning: boolean
    error: string
    fileName: string
    sigma: HydraSigma | null
    graph: HydraGraph | null
    layout: FA2Layout | null
}
