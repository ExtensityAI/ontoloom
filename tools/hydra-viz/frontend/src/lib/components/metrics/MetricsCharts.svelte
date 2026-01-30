<script lang="ts">
	import { onMount, onDestroy } from 'svelte'
	import * as echarts from 'echarts'
	import type { MetricsTimeSeries } from '$lib/api/types'
	import { getChartTheme } from './theme'

	let {
		metrics,
		currentIteration
	}: {
		metrics: MetricsTimeSeries | null
		currentIteration: number
	} = $props()

	let structuralContainer: HTMLDivElement
	let growthContainer: HTMLDivElement
	let structuralChart: echarts.ECharts | null = null
	let growthChart: echarts.ECharts | null = null

	const line = (name: string, color: string, data: unknown[], opts = {}) => ({
		name,
		type: 'line',
		smooth: true,
		lineStyle: { color, width: 2 },
		itemStyle: { color },
		data,
		...opts
	})

	const initCharts = () => {
		if (!structuralContainer || !growthContainer) return
		structuralChart = echarts.init(structuralContainer, undefined, { renderer: 'canvas' })
		growthChart = echarts.init(growthContainer, undefined, { renderer: 'canvas' })
		updateCharts()
	}

	const updateCharts = () => {
		if (!metrics || !structuralChart || !growthChart) return

		const theme = getChartTheme()
		const pts = metrics.points
		const iterations = pts.map((p) => p.iteration)
		const axis = { lineStyle: { color: theme.edge } }
		const label = { color: theme.muted }
		const tooltip = {
			trigger: 'axis',
			backgroundColor: theme.surface,
			borderColor: theme.edge,
			textStyle: { color: theme.fg }
		}
		const yAxis = (extra = {}) => ({
			type: 'value',
			axisLine: axis,
			splitLine: { lineStyle: { color: theme.surface } },
			axisLabel: label,
			...extra
		})

		structuralChart.setOption({
			backgroundColor: 'transparent',
			tooltip,
			legend: { data: ['Classes', 'Depth', 'Branching'], textStyle: label, top: 0 },
			grid: { left: 50, right: 20, top: 40, bottom: 30 },
			xAxis: { type: 'category', data: iterations, axisLine: axis, axisLabel: label },
			yAxis: [yAxis(), yAxis({ splitLine: { show: false } })],
			series: [
				line('Classes', theme.accent, pts.map((p) => p.metrics.class_count), {
					markLine:
						currentIteration >= 0
							? {
									silent: true,
									data: [{ xAxis: currentIteration }],
									lineStyle: { color: theme.accent, type: 'dashed' }
								}
							: undefined
				}),
				line('Depth', theme.ok, pts.map((p) => p.metrics.max_depth), { yAxisIndex: 1 }),
				line(
					'Branching',
					theme.warn,
					pts.map((p) => p.metrics.avg_branching_factor.toFixed(2)),
					{ yAxisIndex: 1 }
				)
			]
		})

		growthChart.setOption({
			backgroundColor: 'transparent',
			tooltip,
			legend: { data: ['Data Props', 'Object Props', 'Coverage'], textStyle: label, top: 0 },
			grid: { left: 50, right: 50, top: 40, bottom: 30 },
			xAxis: { type: 'category', data: iterations, axisLine: axis, axisLabel: label },
			yAxis: [
				yAxis(),
				yAxis({
					max: 100,
					splitLine: { show: false },
					axisLabel: { ...label, formatter: '{value}%' }
				})
			],
			series: [
				line('Data Props', theme.info, pts.map((p) => p.metrics.data_property_count), {
					areaStyle: { opacity: 0.3 }
				}),
				line('Object Props', theme.err, pts.map((p) => p.metrics.object_property_count), {
					areaStyle: { opacity: 0.3 }
				}),
				line(
					'Coverage',
					theme.ok,
					pts.map((p) => (p.metrics.property_coverage * 100).toFixed(1)),
					{ yAxisIndex: 1 }
				)
			]
		})
	}

	const handleResize = () => {
		structuralChart?.resize()
		growthChart?.resize()
	}

	onMount(() => {
		initCharts()
		window.addEventListener('resize', handleResize)
	})

	onDestroy(() => {
		window.removeEventListener('resize', handleResize)
		structuralChart?.dispose()
		growthChart?.dispose()
	})

	$effect(() => {
		if (metrics && structuralChart && growthChart) {
			updateCharts()
		}
	})

	$effect(() => {
		if (structuralChart && currentIteration >= 0) {
			const theme = getChartTheme()
			structuralChart.setOption({
				series: [
					{
						markLine: {
							silent: true,
							data: [{ xAxis: currentIteration }],
							lineStyle: { color: theme.accent, type: 'dashed' }
						}
					}
				]
			})
		}
	})
</script>

<div class="space-y-8">
	<div>
		<h3 class="mb-4 text-sm font-medium text-muted">Structure</h3>
		<div bind:this={structuralContainer} class="h-48"></div>
	</div>

	<div>
		<h3 class="mb-4 text-sm font-medium text-muted">Properties</h3>
		<div bind:this={growthContainer} class="h-48"></div>
	</div>

	{#if !metrics}
		<p class="text-sm text-muted">No metrics data available</p>
	{/if}
</div>
