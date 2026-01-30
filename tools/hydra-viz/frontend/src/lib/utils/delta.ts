/** Format a numeric delta as a string with +/- prefix, or null if unchanged */
export const formatDelta = (curr: number | undefined, prev: number | undefined): string | null => {
	if (curr === undefined || prev === undefined) return null
	const d = curr - prev
	if (d === 0) return null
	return d > 0 ? `+${d}` : `${d}`
}

/** Get the CSS class for a delta indicator */
export const getDeltaClass = (
	curr: number | undefined,
	prev: number | undefined,
	invert = false
): string => {
	if (curr === undefined || prev === undefined) return ''
	const d = curr - prev
	if (d === 0) return 'text-faint'
	const isPositive = invert ? d < 0 : d > 0
	return isPositive ? 'text-ok' : 'text-err'
}
