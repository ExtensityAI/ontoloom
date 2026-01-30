import { ACTIVE_EDGE_SIZE, BASE_NODE_SIZE, NODE_SIZE_MULTIPLIER, GRAPH_THEME } from './theme'
import type { EdgeAttributes, NodeAttributes } from './types'
import type { EdgeDisplayData, NodeDisplayData } from 'sigma/types'
import type { NodeSelection } from './selection'

type SelectionGetter = () => NodeSelection | null

const resolveNodeSize = (inverseLevel: number) =>
	BASE_NODE_SIZE + inverseLevel * NODE_SIZE_MULTIPLIER

const resolveLevelColor = (level: number): string => {
	const levels = GRAPH_THEME.node.levels
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
	type: 'arrow',
	color: GRAPH_THEME.edge,
	size: data.size,
	zIndex: 0,
	label: ''
})

type NodeRelation = 'unrelated' | 'selected' | 'parent' | 'child'

const getNodeRelation = (node: string, active: NodeSelection): NodeRelation => {
	if (active.node === node) return 'selected'
	if (active.parents.has(node)) return 'parent'
	if (active.children.has(node)) return 'child'
	return 'unrelated'
}

export const createNodeReducer =
	(getActiveSelection: SelectionGetter) => (node: string, data: NodeAttributes) => {
		const active = getActiveSelection()
		const base = getBaseNodeData(data)

		if (!active) return base

		const rel = getNodeRelation(node, active)

		if (rel === 'unrelated') {
			return {
				...base,
				color: GRAPH_THEME.inactive,
				label: ''
			}
		}

		return {
			...base,
			color: GRAPH_THEME.node.focus[rel],
			label: data.label,
			zIndex: 2,
			forceLabel: true
		}
	}

const reduceHierarchyEdge = (
	data: EdgeAttributes,
	active: NodeSelection,
	base: Partial<EdgeDisplayData>
) => {
	const { source, target } = data

	let color
	if (source === active.node) color = GRAPH_THEME.node.focus.selected
	else if (target === active.node) color = GRAPH_THEME.node.focus.child
	else if (active.parents.has(source)) color = GRAPH_THEME.node.focus.parent
	else return base

	return { ...base, color, size: ACTIVE_EDGE_SIZE, zIndex: 1, label: 'isA', forceLabel: true }
}

export const createEdgeReducer =
	(getActiveSelection: SelectionGetter) => (_edge: string, data: EdgeAttributes) => {
		const active = getActiveSelection()
		const base = getBaseEdgeData(data)

		if (!active) return base
		if (data.label === 'isA') return reduceHierarchyEdge(data, active, base)

		return { ...base, color: GRAPH_THEME.edge }
	}
