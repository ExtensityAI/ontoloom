<script lang="ts">
	import * as echarts from 'echarts'
	import type { MetricsTimeSeries, MetricsTimeSeriesPoint } from '$lib/api/types'
	import { type ChartTheme, getChartTheme } from './theme'

	let {
		metrics,
		currentIteration
	}: {
		metrics: MetricsTimeSeries | null
		currentIteration: number
	} = $props()

	let structuralContainer: HTMLDivElement
	let growthContainer: HTMLDivElement
	let structuralChart: echarts.ECharts | null = $state(null)
	let growthChart: echarts.ECharts | null = $state(null)

	const line = (name: string, color: string, data: unknown[], opts = {}) => ({
		name,
		type: 'line',
		smooth: true,
		lineStyle: { color, width: 2 },
		itemStyle: { color },
		data,
		...opts
	})

	const buildStructuralOption = (
		theme: ChartTheme,
		pts: MetricsTimeSeriesPoint[],
		currentIter: number
	) => {
		const iterations = pts.map((p) => p.iteration)
		const axis = { lineStyle: { color: theme.edge } }
		const label = { color: theme.muted }

		return {
			backgroundColor: 'transparent',
			tooltip: {
				trigger: 'axis',
				backgroundColor: theme.surface,
				borderColor: theme.edge,
				textStyle: { color: theme.fg }
			},
			legend: { data: ['Classes', 'Depth', 'Branching'], textStyle: label, top: 0 },
			grid: { left: 50, right: 20, top: 40, bottom: 30 },
			xAxis: { type: 'category', data: iterations, axisLine: axis, axisLabel: label },
			yAxis: [
				{ type: 'value', axisLine: axis, splitLine: { lineStyle: { color: theme.surface } }, axisLabel: label },
				{ type: 'value', axisLine: axis, splitLine: { show: false }, axisLabel: label }
			],
			series: [
				line('Classes', theme.accent, pts.map((p) => p.metrics.class_count), {
					markLine:
						currentIter >= 0
							? {
									silent: true,
									data: [{ xAxis: currentIter }],
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
		}
	}

	const buildGrowthOption = (theme: ChartTheme, pts: MetricsTimeSeriesPoint[]) => {
		const iterations = pts.map((p) => p.iteration)
		const axis = { lineStyle: { color: theme.edge } }
		const label = { color: theme.muted }

		return {
			backgroundColor: 'transparent',
			tooltip: {
				trigger: 'axis',
				backgroundColor: theme.surface,
				borderColor: theme.edge,
				textStyle: { color: theme.fg }
			},
			legend: { data: ['Data Props', 'Object Props', 'Coverage'], textStyle: label, top: 0 },
			grid: { left: 50, right: 50, top: 40, bottom: 30 },
			xAxis: { type: 'category', data: iterations, axisLine: axis, axisLabel: label },
			yAxis: [
				{ type: 'value', axisLine: axis, splitLine: { lineStyle: { color: theme.surface } }, axisLabel: label },
				{
					type: 'value',
					axisLine: axis,
					splitLine: { show: false },
					axisLabel: { ...label, formatter: '{value}%' },
					max: 100
				}
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
		}
	}

	// Lifecycle: init and dispose charts when containers are ready
	$effect(() => {
		if (!structuralContainer || !growthContainer) return

		const sChart = echarts.init(structuralContainer, undefined, { renderer: 'canvas' })
		const gChart = echarts.init(growthContainer, undefined, { renderer: 'canvas' })
		structuralChart = sChart
		growthChart = gChart

		const handleResize = () => {
			sChart.resize()
			gChart.resize()
		}
		window.addEventListener('resize', handleResize)

		return () => {
			window.removeEventListener('resize', handleResize)
			sChart.dispose()
			gChart.dispose()
			structuralChart = null
			growthChart = null
		}
	})

	// Update chart options when data or iteration changes
	$effect(() => {
		if (!structuralChart || !growthChart || !metrics) return
		const theme = getChartTheme()
		structuralChart.setOption(buildStructuralOption(theme, metrics.points, currentIteration))
		growthChart.setOption(buildGrowthOption(theme, metrics.points))
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
