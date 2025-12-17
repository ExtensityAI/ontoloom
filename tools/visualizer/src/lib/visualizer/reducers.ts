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
        const hasSelection = active.node !== null

        const relationColor = isSelected
            ? COLORS.node.selected
            : isParent
              ? COLORS.node.parent
              : isChild
                ? COLORS.node.child
                : null
        const color =
            relationColor ??
            (hasSelection
                ? COLORS.node.inactive
                : (LEVEL_COLORS[data.level] ??
                  LEVEL_COLORS[LEVEL_COLORS.length - 1]!))

        return {
            ...data,
            color,
            size: BASE_NODE_SIZE + data.inverseLevel * NODE_SIZE_MULTIPLIER,
            zIndex: isSelected ? 2 : isParent || isChild ? 1 : 0,
        }
    }

export const createEdgeReducer =
    (getActiveSelection: SelectionGetter) =>
    (edge: string, data: EdgeAttributes) => {
        const active = getActiveSelection()
        const activeNode = active.node
        const isConnected = active.connectedEdges.has(edge)
        const hasSelection = activeNode !== null
        const isHierarchy = data.tag === "hierarchy"

        const palette = isHierarchy
            ? COLORS.edge.hierarchy
            : COLORS.edge.property
        const color = !hasSelection
            ? palette.default
            : isConnected
              ? palette.active
              : palette.inactive

        const showLabel = data.source === activeNode || data.target === activeNode

        return {
            ...data,
            color,
            size: isConnected ? ACTIVE_EDGE_SIZE : data.size,
            zIndex: isConnected ? 1 : 0,
            label: showLabel ? data.label : "",
        }
    }
