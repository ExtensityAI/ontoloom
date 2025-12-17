import type FA2Layout from "graphology-layout-forceatlas2/worker"
import type { HydraSigma, HydraGraph, NodeAttributes } from "../graph/types"



export interface ViewState {
    hoveredNode: string | null
    pinnedNode: string | null
    searchVisible: boolean
}


export interface RuntimeState {
    isLoading: boolean
    isLayoutRunning: boolean
    fileName: string
    sigma: HydraSigma | null
    graph: HydraGraph | null
    layout: FA2Layout | null
}
