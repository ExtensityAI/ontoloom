const getCssVar = (name: string): string =>
	getComputedStyle(document.documentElement).getPropertyValue(name).trim()

export interface ChartTheme {
	surface: string
	edge: string
	muted: string
	fg: string
	accent: string
	ok: string
	warn: string
	info: string
	err: string
}

let cached: ChartTheme | null = null

export const getChartTheme = (): ChartTheme => {
	if (cached) return cached
	cached = {
		surface: getCssVar('--color-surface'),
		edge: getCssVar('--color-edge'),
		muted: getCssVar('--color-muted'),
		fg: getCssVar('--color-fg'),
		accent: getCssVar('--color-accent'),
		ok: getCssVar('--color-ok'),
		warn: getCssVar('--color-warn'),
		info: getCssVar('--color-info'),
		err: getCssVar('--color-err')
	}
	return cached
}

export const chartAxis = (theme: ChartTheme) => ({
	line: { lineStyle: { color: theme.edge } },
	label: { color: theme.muted },
	splitLine: { lineStyle: { color: theme.surface } }
})

export const chartTooltip = (theme: ChartTheme) => ({
	trigger: 'axis' as const,
	backgroundColor: theme.surface,
	borderColor: theme.edge,
	textStyle: { color: theme.fg }
})
