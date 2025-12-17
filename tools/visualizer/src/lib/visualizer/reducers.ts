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
    const color = COLORS.inactive

    return {
        type: "arrow",
        color: color,
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

        if(rel === "unrelated") return {
            ...base,
            color: COLORS.inactive,
            label: ""
        }

        return { ...base, color: COLORS.node.focus[rel], label: data.label, zIndex: 1, forceLabel: true }
    }

const reduceHierarchyEdge = (
    edge: string,
    data: EdgeAttributes,
    active: NodeSelection,
    base: Partial<EdgeDisplayData>,
) => {

    const { source, target } = data
    const node = active.node

    let color;

    if(source === node) {
        // node to parent
        color = COLORS.node.focus.selected
    } else if(target === node) {
        // child to node
        color = COLORS.node.focus.child
    } else if(active.parents.has(source)) {
        // parent to parent, we do not track child to child
        color = COLORS.node.focus.parent
    } else {
        // unrelated
        return base
    }

    return {
        ...base,
        color,
        size: ACTIVE_EDGE_SIZE,
        zIndex: 1,
        label: "isA",
        forceLabel: true
    }

    


}

export const createEdgeReducer =
    (getActiveSelection: SelectionGetter) =>
    (edge: string, data: EdgeAttributes) => {
        const active = getActiveSelection()
        const base = getBaseEdgeData(data)

        if (!active) return base

        if(data.label === "isA") {
            return reduceHierarchyEdge(edge, data, active, base)
        }

        return {
            ...base,
            color: COLORS.inactive,
        }
    }
