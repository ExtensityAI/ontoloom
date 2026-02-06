<script lang="ts">
	import type { Metric } from '$lib/api/types'
	import { getChartTheme, chartAxis, chartTooltip } from './theme'
	import { countValues } from '$lib/utils/format'
	import Chart from './Chart.svelte'

	let {
		title,
		metric,
		height = 160
	}: {
		title: string
		metric: Metric | null
		height?: number
	} = $props()

	const values = $derived(metric?.raw ?? [])
	const hasData = $derived(values.length > 0)
	const histogram = $derived.by(() => countValues(values))

	let options: Record<string, unknown> | null = $state(null)

	$effect(() => {
		if (!hasData) {
			options = null
			return
		}
		const theme = getChartTheme()
		const ax = chartAxis(theme)
		options = {
			backgroundColor: 'transparent',
			tooltip: chartTooltip(theme),
			grid: { left: 40, right: 15, top: 10, bottom: 30 },
			xAxis: {
				type: 'category',
				data: histogram.labels,
				axisLine: ax.line,
				axisLabel: { ...ax.label, fontSize: 10, hideOverlap: true }
			},
			yAxis: {
				type: 'value',
				axisLine: ax.line,
				axisLabel: { ...ax.label, fontSize: 10 },
				splitLine: ax.splitLine
			},
			series: [
				{
					type: 'bar',
					data: histogram.counts,
					itemStyle: { color: theme.accent, opacity: 0.8 },
					barCategoryGap: '0%',
					barGap: '0%'
				}
			]
		}
	})
</script>

<div class="border border-edge p-4">
	<div class="mb-3 flex items-center justify-between">
		<h3 class="text-sm font-medium text-muted">{title}</h3>
		{#if metric}
			<span class="text-xs text-muted">{metric.raw.length} values</span>
		{/if}
	</div>
	{#if !hasData}
		<p class="text-sm text-muted">No distribution data</p>
	{:else}
		<Chart {height} {options} />
	{/if}
</div>
