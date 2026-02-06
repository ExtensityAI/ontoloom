<script lang="ts">
	import type { IterationSummary } from '$lib/api/types'
	import { coverage } from '$lib/utils/format'
	import LineChart from './LineChart.svelte'

	let { iterations }: { iterations: IterationSummary[] } = $props()

	const withMetrics = $derived(
		iterations.filter(
			(i): i is IterationSummary & { ontology_metrics: NonNullable<IterationSummary['ontology_metrics']> } =>
				i.ontology_metrics !== null
		)
	)

	const labels = $derived(withMetrics.map((i) => i.index))

	const structureSeries = $derived.by(() => [
		{
			name: 'Classes',
			color: 'accent' as const,
			data: withMetrics.map((i) => i.ontology_metrics.counts.n_classes)
		},
		{
			name: 'Depth',
			color: 'ok' as const,
			data: withMetrics.map((i) => i.ontology_metrics.distributions.class_depth.max),
			yAxisIndex: 1
		},
		{
			name: 'Branching',
			color: 'warn' as const,
			data: withMetrics.map((i) => i.ontology_metrics.distributions.subclasses_per_class.mean),
			yAxisIndex: 1
		}
	])

	const propertySeries = $derived.by(() => [
		{
			name: 'Data Props',
			color: 'info' as const,
			data: withMetrics.map((i) => i.ontology_metrics.counts.n_data_properties),
			area: true
		},
		{
			name: 'Object Props',
			color: 'err' as const,
			data: withMetrics.map((i) => i.ontology_metrics.counts.n_object_properties),
			area: true
		},
		{
			name: 'Coverage',
			color: 'ok' as const,
			data: withMetrics.map((i) => +(coverage(i.ontology_metrics) * 100).toFixed(1)),
			yAxisIndex: 1
		}
	])
</script>

<div class="space-y-8">
	{#if withMetrics.length}
		<LineChart
			title="Structure"
			{labels}
			series={structureSeries}
			secondaryAxis={true}
			height={192}
		/>
		<LineChart
			title="Properties"
			{labels}
			series={propertySeries}
			secondaryAxis="percent"
			height={192}
		/>
	{:else}
		<p class="text-sm text-muted">No metrics data available</p>
	{/if}
</div>
