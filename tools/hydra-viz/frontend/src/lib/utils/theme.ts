/** Resolve a CSS custom property value at runtime */
export const getCssVar = (name: string): string =>
	getComputedStyle(document.documentElement).getPropertyValue(name).trim()

/** Theme colors for the graph visualizer */
export interface VisualizerThemeColors {
	label: string
	inactive: string
	edge: string
	node: {
		focus: {
			selected: string
			parent: string
			child: string
		}
		levels: string[]
	}
}

/** Theme colors for charts */
export interface ChartThemeColors {
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

// Explicit hex colors for graph visualization (Sigma.js needs actual colors, not CSS vars)
// These match the Tailwind color palette used in layout.css
const GRAPH_COLORS = {
	// stone palette
	stone100: '#f5f5f4',
	stone400: '#a8a29e',
	stone800: '#292524',
	// semantic
	sky400: '#38bdf8',
	blue400: '#60a5fa',
	amber400: '#fbbf24',
	// cyan levels (depth visualization)
	cyan800: '#155e75',
	cyan700: '#0e7490',
	cyan600: '#0891b2',
	cyan500: '#06b6d4',
	cyan400: '#22d3ee',
	cyan300: '#67e8f9'
}

/** Get visualizer theme colors (explicit hex for Sigma.js compatibility) */
export const getVisualizerTheme = (): VisualizerThemeColors => ({
	label: GRAPH_COLORS.stone100,
	inactive: GRAPH_COLORS.stone400,
	edge: GRAPH_COLORS.stone800,
	node: {
		focus: {
			selected: GRAPH_COLORS.sky400,
			parent: GRAPH_COLORS.blue400,
			child: GRAPH_COLORS.amber400
		},
		levels: [
			GRAPH_COLORS.cyan800,
			GRAPH_COLORS.cyan700,
			GRAPH_COLORS.cyan600,
			GRAPH_COLORS.cyan500,
			GRAPH_COLORS.cyan400,
			GRAPH_COLORS.cyan300
		]
	}
})

/** Get chart theme colors from CSS variables */
export const getChartTheme = (): ChartThemeColors => ({
	surface: getCssVar('--color-surface'),
	edge: getCssVar('--color-edge'),
	muted: getCssVar('--color-muted'),
	fg: getCssVar('--color-fg'),
	accent: getCssVar('--color-accent'),
	ok: getCssVar('--color-ok'),
	warn: getCssVar('--color-warn'),
	info: getCssVar('--color-info'),
	err: getCssVar('--color-err')
})
