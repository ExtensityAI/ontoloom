import type { IterationDetail } from '$lib/api/types'

type Operation = IterationDetail['ops'][number]

export interface GroupedOperations {
	adds: Operation[]
	updates: Operation[]
	deletes: Operation[]
	merges: Operation[]
}

export const groupOperations = (ops: Operation[]): GroupedOperations => {
	const grouped = { adds: [], updates: [], deletes: [], merges: [] } as GroupedOperations
	for (const op of ops) {
		if (op.op.startsWith('add')) grouped.adds.push(op)
		else if (op.op.startsWith('update')) grouped.updates.push(op)
		else if (op.op.startsWith('del')) grouped.deletes.push(op)
		else if (op.op === 'merge_classes') grouped.merges.push(op)
	}
	return grouped
}

export const displayName = (op: Operation): string => {
	if ('name' in op) return op.name
	if ('target_name' in op) return op.target_name
	return ''
}

export const badgeClass = (op: string): string => {
	if (op.startsWith('add')) return 'bg-ok/10 text-ok border-ok/20'
	if (op.startsWith('del')) return 'bg-err/10 text-err border-err/20'
	if (op.startsWith('update')) return 'bg-warn/10 text-warn border-warn/20'
	if (op === 'merge_classes') return 'bg-info/10 text-info border-info/20'
	return 'bg-surface/70 text-muted border-edge'
}
