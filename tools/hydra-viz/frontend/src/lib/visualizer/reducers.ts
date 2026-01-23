import {
    ACTIVE_EDGE_SIZE,
    BASE_NODE_SIZE,
    NODE_SIZE_MULTIPLIER,
    getThemeColors,
} from "./constants"
import type { EdgeAttributes, NodeAttributes } from "../graph/types"
import type { EdgeDisplayData, NodeDisplayData } from "sigma/types"
import type { NodeSelection } from "./selection"
import type { OntologyDiff } from "$lib/utils/diff"

type SelectionGetter = () => NodeSelection | null
type DiffGetter = () => OntologyDiff | undefined

// Get colors (always returns valid colors object)
const colors = () => getThemeColors()

const resolveNodeSize = (inverseLevel: number) =>
    BASE_NODE_SIZE + inverseLevel * NODE_SIZE_MULTIPLIER

const resolveLevelColor = (level: number): string => {
    const c = colors()
    return c.node.levels[level] ?? c.node.levels[c.node.levels.length - 1]
}

type DiffStatus = "added" | "removed" | "modified" | "unchanged"

const getNodeDiffStatus = (node: string, diff: OntologyDiff | undefined): DiffStatus => {
    if (!diff) return "unchanged"
    if (diff.classes.added.includes(node)) return "added"
    if (diff.classes.removed.includes(node)) return "removed"
    if (diff.classes.modified.includes(node)) return "modified"
    return "unchanged"
}

const getBaseNodeData = (data: NodeAttributes, diffStatus: DiffStatus): Partial<NodeDisplayData> => {
    const c = colors()
    const baseColor = resolveLevelColor(data.level)

    // Apply diff styling - use color directly since Sigma doesn't support borders
    let color = baseColor
    let size = resolveNodeSize(data.inverseLevel)

    switch (diffStatus) {
        case "added":
            color = c.diff.added
            size = size * 1.3 // Slightly larger
            break
        case "removed":
            color = c.diff.removed
            size = size * 0.8 // Slightly smaller
            break
        case "modified":
            color = c.diff.modified
            size = size * 1.2
            break
    }

    return {
        color,
        size,
        zIndex: diffStatus !== "unchanged" ? 1 : 0,
        label: data.label,
        x: data.x,
        y: data.y,
    }
}

const getBaseEdgeData = (data: EdgeAttributes): Partial<EdgeDisplayData> => ({
    type: "arrow",
    color: colors().inactive,
    size: data.size,
    zIndex: 0,
    label: "",
})

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
    (getActiveSelection: SelectionGetter, getDiff?: DiffGetter) =>
    (node: string, data: NodeAttributes) => {
        const active = getActiveSelection()
        const diff = getDiff?.()
        const diffStatus = getNodeDiffStatus(node, diff)
        const base = getBaseNodeData(data, diffStatus)

        if (!active) return base

        const rel = getNodeRelation(node, active)
        const c = colors()

        if (rel === "unrelated") {
            // For diff nodes, keep their color visible even when unrelated
            if (diffStatus !== "unchanged") {
                return {
                    ...base,
                    label: data.label,
                }
            }
            return {
                ...base,
                color: c.inactive,
                label: "",
            }
        }

        return {
            ...base,
            color: c.node.focus[rel],
            label: data.label,
            zIndex: 2,
            forceLabel: true,
        }
    }

const reduceHierarchyEdge = (
    data: EdgeAttributes,
    active: NodeSelection,
    base: Partial<EdgeDisplayData>,
) => {
    const c = colors()
    const { source, target } = data

    let color
    if (source === active.node) color = c.node.focus.selected
    else if (target === active.node) color = c.node.focus.child
    else if (active.parents.has(source)) color = c.node.focus.parent
    else return base

    return { ...base, color, size: ACTIVE_EDGE_SIZE, zIndex: 1, label: "isA", forceLabel: true }
}

export const createEdgeReducer =
    (getActiveSelection: SelectionGetter, _getDiff?: DiffGetter) =>
    (_edge: string, data: EdgeAttributes) => {
        const active = getActiveSelection()
        const base = getBaseEdgeData(data)

        if (!active) return base
        if (data.label === "isA") return reduceHierarchyEdge(data, active, base)

        return { ...base, color: colors().inactive }
    }
