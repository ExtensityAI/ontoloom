import type { OntologyMetrics } from '$lib/api/types'

export const countValues = (raw: number[]) => {
	if (!raw.length) return { labels: [] as string[], counts: [] as number[] }

	let min = raw[0]
	let max = raw[0]
	let allIntegers = Number.isInteger(raw[0])
	for (const v of raw) {
		if (v < min) min = v
		if (v > max) max = v
		if (allIntegers && !Number.isInteger(v)) allIntegers = false
	}
	if (min === max) {
		return { labels: [String(min)], counts: [raw.length] }
	}

	const targetBins = Math.min(40, Math.max(4, Math.ceil(Math.sqrt(raw.length))))
	if (allIntegers) {
		const span = Math.max(1, Math.round(max - min + 1))
		const width = Math.max(1, Math.ceil(span / targetBins))
		const bins = Math.ceil(span / width)
		const counts = Array.from({ length: bins }, () => 0)
		for (const v of raw) {
			const idx = Math.min(bins - 1, Math.floor((v - min) / width))
			counts[idx] += 1
		}
		const labels = counts.map((_, i) => {
			const start = Math.round(min + i * width)
			const end = Math.min(Math.round(max), start + width - 1)
			return start === end ? String(start) : `${start}-${end}`
		})
		return { labels, counts }
	}

	const width = (max - min) / targetBins
	const counts = Array.from({ length: targetBins }, () => 0)
	for (const v of raw) {
		const idx = Math.min(targetBins - 1, Math.floor((v - min) / width))
		counts[idx] += 1
	}
	const precision = width >= 1 ? 0 : width >= 0.1 ? 1 : 2
	const format = (value: number) => Number(value.toFixed(precision)).toString()
	const labels = counts.map((_, i) => {
		const start = min + i * width
		const end = i === targetBins - 1 ? max : start + width
		return `${format(start)}-${format(end)}`
	})
	return { labels, counts }
}

export const coverage = (m: OntologyMetrics) => {
	const total = m.counts.n_classes
	if (!total) return 0
	return (total - m.counts.classes_with_no_properties) / total
}
