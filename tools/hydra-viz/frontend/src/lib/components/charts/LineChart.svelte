<script lang="ts">
	import { getChartTheme, chartAxis, chartTooltip, type ChartTheme } from './theme'
	import Chart from './Chart.svelte'

	type ColorKey = keyof ChartTheme

	interface LineSeries {
		name: string
		data: (number | null)[]
		color?: ColorKey
		yAxisIndex?: number
		area?: boolean
		smooth?: boolean
	}

	let {
		title,
		labels,
		series,
		percent = false,
		secondaryAxis = false,
		height = 200
	}: {
		title: string
		labels: (string | number)[]
		series: LineSeries[]
		percent?: boolean
		secondaryAxis?: boolean | 'percent'
		height?: number
	} = $props()

	let options: Record<string, unknown> | null = $state(null)

	$effect(() => {
		const theme = getChartTheme()
		const ax = chartAxis(theme)

		const makeYAxis = (pct: boolean) =>
			pct
				? { type: 'value', axisLine: ax.line, splitLine: ax.splitLine, axisLabel: { ...ax.label, formatter: '{value}%' }, max: 100 }
				: { type: 'value', axisLine: ax.line, splitLine: ax.splitLine, axisLabel: ax.label }

		const yAxes = [makeYAxis(percent)]
		if (secondaryAxis) {
			const sec = makeYAxis(secondaryAxis === 'percent')
			sec.splitLine = { show: false } as any
			yAxes.push(sec)
		}

		const lineSeries = series.map((s) => {
			const colorKey = s.color ?? 'accent'
			const color = theme[colorKey]
			return {
				name: s.name,
				type: 'line',
				smooth: s.smooth ?? true,
				lineStyle: { color, width: 2 },
				itemStyle: { color },
				data: s.data,
				yAxisIndex: s.yAxisIndex ?? 0,
				areaStyle: s.area ? { opacity: 0.2 } : undefined
			}
		})

		options = {
			backgroundColor: 'transparent',
			tooltip: chartTooltip(theme),
			legend: { data: series.map((s) => s.name), textStyle: ax.label, top: 0 },
			grid: { left: 50, right: secondaryAxis ? 50 : 20, top: 40, bottom: 30 },
			xAxis: { type: 'category', data: labels, axisLine: ax.line, axisLabel: ax.label },
			yAxis: yAxes,
			series: lineSeries
		}
	})
</script>

<div>
	<h3 class="mb-4 text-sm font-medium text-muted">{title}</h3>
	<Chart {height} {options} />
</div>
