import {
    ACTIVE_EDGE_SIZE,
    BASE_NODE_SIZE,
    COLORS,
    LEVEL_COLORS,
    NODE_SIZE_MULTIPLIER,
} from "./constants"
import type { EdgeAttributes, NodeAttributes } from "../graph/types"
import type { NodeSelection } from "./types"

type SelectionGetter = () => NodeSelection

export const createNodeReducer =
    (getActiveSelection: SelectionGetter) =>
    (node: string, data: NodeAttributes) => {
        const active = getActiveSelection()
        const isSelected = active.node === node
        const isParent = active.parents.has(node)
        const isChild = active.children.has(node)
        const isRelated = isSelected || isParent || isChild
        const hasSelection = active.node !== null

        let color: string
        if (isSelected) {
            color = COLORS.node.selected
        } else if (isParent) {
            color = COLORS.node.parent
        } else if (isChild) {
            color = COLORS.node.child
        } else if (hasSelection) {
            color = COLORS.node.inactive
        } else {
            color = LEVEL_COLORS[data.level] ?? LEVEL_COLORS.at(-1)!
        }

        return {
            ...data,
            color,
            size: BASE_NODE_SIZE + data.inverseLevel * NODE_SIZE_MULTIPLIER,
            zIndex: isSelected ? 2 : isRelated ? 1 : 0,
        }
    }

export const createEdgeReducer =
    (getActiveSelection: SelectionGetter) =>
    (edge: string, data: EdgeAttributes) => {
        const active = getActiveSelection()
        const isConnected = active.connectedEdges.has(edge)
        const hasSelection = active.node !== null
        const isHierarchy = data.tag === "hierarchy"

        const palette = isHierarchy
            ? COLORS.edge.hierarchy
            : COLORS.edge.property
        const color = hasSelection
            ? isConnected
                ? palette.active
                : palette.inactive
            : palette.default

        const showLabel =
            data.source === active.node || data.target === active.node

        return {
            ...data,
            color,
            size: isConnected ? ACTIVE_EDGE_SIZE : data.size,
            zIndex: isConnected ? 1 : 0,
            label: showLabel ? data.label : "",
        }
    }
