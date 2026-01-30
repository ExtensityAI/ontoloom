import type { IterationDetail } from '$lib/api/types'

type Operation = IterationDetail['ops'][number]

export interface GroupedOperations {
	adds: Operation[]
	updates: Operation[]
	deletes: Operation[]
	merges: Operation[]
}

/** Group operations by their type */
export const groupOperations = (ops: Operation[]): GroupedOperations => ({
	adds: ops.filter((op) => op.op.startsWith('add')),
	updates: ops.filter((op) => op.op.startsWith('update')),
	deletes: ops.filter((op) => op.op.startsWith('del')),
	merges: ops.filter((op) => op.op === 'merge_classes')
})

/** Get the display name for an operation */
export const getOperationDisplayName = (op: Operation): string => {
	if ('name' in op) return op.name
	if ('target_name' in op) return op.target_name
	return ''
}

/** Get the CSS class for an operation badge */
export const getOperationBadgeClass = (op: string): string => {
	if (op.startsWith('add')) return 'bg-ok/10 text-ok border-ok/20'
	if (op.startsWith('del')) return 'bg-err/10 text-err border-err/20'
	if (op.startsWith('update')) return 'bg-warn/10 text-warn border-warn/20'
	if (op === 'merge_classes') return 'bg-info/10 text-info border-info/20'
	return 'bg-surface/70 text-muted border-edge'
}
