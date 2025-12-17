import {
    ACTIVE_EDGE_SIZE,
    BASE_NODE_SIZE,
    COLORS,
    NODE_SIZE_MULTIPLIER,
} from "./constants"
import type { EdgeAttributes, NodeAttributes } from "../graph/types"
import type { EdgeDisplayData, NodeDisplayData } from "sigma/types"
import type { NodeSelection } from "./selection"

type SelectionGetter = () => NodeSelection | null


const resolveNodeSize = (inverseLevel: number) =>
    BASE_NODE_SIZE + inverseLevel * NODE_SIZE_MULTIPLIER

const resolveLevelColor = (level: number): string =>
    COLORS.node.levels[level] ??
    COLORS.node.levels[COLORS.node.levels.length - 1]

const getBaseNodeData = (data: NodeAttributes): Partial<NodeDisplayData> => ({
    color: resolveLevelColor(data.level),
    size: resolveNodeSize(data.inverseLevel),
    zIndex: 0,
    label: data.label,
    x: data.x,
    y: data.y,
})

const getBaseEdgeData = (data: EdgeAttributes): Partial<EdgeDisplayData> => {
    const isHierarchy = data.tag === "hierarchy"
    const palette = isHierarchy ? COLORS.edge.hierarchy : COLORS.edge.property

    return {
        type: "arrow",
        color: palette.default,
        size: data.size,
        zIndex: 0,
        label: "",
    }
}

type NodeRelation = "unrelated" | "selected" | "parent" | "child"

const getNodeRelation = (
    node: string,
    active: NodeSelection,
): NodeRelation => {
    if (active.node === node) return "selected"
    if (active.parents.has(node)) return "parent"
    if (active.children.has(node)) return "child"
    return "unrelated"
}

export const createNodeReducer =
    (getActiveSelection: SelectionGetter) =>
    (node: string, data: NodeAttributes) => {
        const active = getActiveSelection()
        const base = getBaseNodeData(data)

        if (!active) return base

        const rel = getNodeRelation(node, active)
        const color = rel === "unrelated" ? COLORS.inactive : COLORS.node.focus[rel]

        // don't show labels for unrelated nodes
        const label = rel === "unrelated" ? "" : data.label

        return { ...base, color, label }
    }

export const createEdgeReducer =
    (getActiveSelection: SelectionGetter) =>
    (edge: string, data: EdgeAttributes) => {
        const active = getActiveSelection()
        const base = getBaseEdgeData(data)

        if (!active) return base

        const palette = COLORS.edge[data.tag]

        if(data.label === "isA") {
            // hierarchy edge
            if (
                active.node === data.source ||
                active.node === data.target ||
                active.parents.has(data.source) ||
                active.children.has(data.target)
            ) {
                return {
                    ...base,
                    color: COLORS.node.focus.selected,
                    size: ACTIVE_EDGE_SIZE,
                }
            }
        }

        return {
            ...base,
            color: COLORS.inactive,
        }
    }
