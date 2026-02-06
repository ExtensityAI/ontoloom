import type { EdgeDisplayData, NodeDisplayData } from "sigma/types"
import type { NodeSelection } from "./types"
import { activeEdgeSize, baseNodeSize, graphTheme, nodeSizeMultiplier } from "./theme"
import type { EdgeAttributes, NodeAttributes } from "./types"

type SelectionGetter = () => NodeSelection | null
type HoverGetter = () => string | null

const resolveNodeSize = (inverseLevel: number) => baseNodeSize + inverseLevel * nodeSizeMultiplier

const resolveLevelColor = (level: number): string => {
  const levels = graphTheme.node.levels
  return levels[level] ?? levels[levels.length - 1]
}

const getBaseNodeData = (data: NodeAttributes): Partial<NodeDisplayData> => ({
  color: resolveLevelColor(data.level),
  size: resolveNodeSize(data.inverseLevel),
  zIndex: 0,
  label: data.label,
  x: data.x,
  y: data.y
})

const getBaseEdgeData = (data: EdgeAttributes): Partial<EdgeDisplayData> => ({
  type: "arrow",
  color: graphTheme.edge,
  size: data.size,
  zIndex: 0,
  label: ""
})

type NodeRelation = "unrelated" | "selected" | "parent" | "child"

const getNodeRelation = (node: string, active: NodeSelection): NodeRelation => {
  if (active.node === node) return "selected"
  if (active.parents.has(node)) return "parent"
  if (active.children.has(node)) return "child"
  return "unrelated"
}

export const createNodeReducer =
  (getActiveSelection: SelectionGetter, getHoveredNode: HoverGetter) =>
  (node: string, data: NodeAttributes) => {
    const active = getActiveSelection()
    const hovered = getHoveredNode()
    const base = getBaseNodeData(data)

    if (!active) {
      if (node === hovered) {
        return { ...base, labelColor: graphTheme.labelHover, forceLabel: true }
      }
      return base
    }

    const rel = getNodeRelation(node, active)

    if (rel === "unrelated") {
      const inactiveNode = {
        ...base,
        color: graphTheme.inactive,
        label: ""
      }
      if (node === hovered) {
        return {
          ...inactiveNode,
          label: data.label,
          labelColor: graphTheme.labelHover,
          forceLabel: true
        }
      }
      return inactiveNode
    }

    const focusedNode = {
      ...base,
      color: graphTheme.node.focus[rel],
      label: data.label,
      zIndex: 2,
      forceLabel: true
    }
    if (node === hovered) {
      return { ...focusedNode, labelColor: graphTheme.labelHover }
    }
    return focusedNode
  }

const reduceHierarchyEdge = (
  data: EdgeAttributes,
  active: NodeSelection,
  base: Partial<EdgeDisplayData>
) => {
  const { source, target } = data

  let color
  if (source === active.node) color = graphTheme.node.focus.selected
  else if (target === active.node) color = graphTheme.node.focus.child
  else if (active.parents.has(source)) color = graphTheme.node.focus.parent
  else return base

  return { ...base, color, size: activeEdgeSize, zIndex: 1, label: "isA", forceLabel: true }
}

export const createEdgeReducer =
  (getActiveSelection: SelectionGetter) => (_edge: string, data: EdgeAttributes) => {
    const active = getActiveSelection()
    const base = getBaseEdgeData(data)

    if (!active) return base
    if (data.label === "isA") return reduceHierarchyEdge(data, active, base)

    return { ...base, color: graphTheme.edge }
  }
