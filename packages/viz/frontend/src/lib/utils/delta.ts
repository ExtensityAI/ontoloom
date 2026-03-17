export const computeDelta = (
	curr: number | undefined,
	prev: number | undefined
): { text: string | null; color: string } => {
	if (curr === undefined || prev === undefined) return { text: null, color: '' }
	const d = curr - prev
	if (d === 0) return { text: null, color: 'text-faint' }
	return {
		text: d > 0 ? `+${d}` : `${d}`,
		color: d > 0 ? 'text-ok' : 'text-err'
	}
}
