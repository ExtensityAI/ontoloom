/** Theme colors for the graph visualizer */
export interface GraphTheme {
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

// Explicit hex colors for graph visualization (Sigma.js needs actual colors, not CSS vars)
// These match the Tailwind color palette used in layout.css
const COLORS = {
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

export const GRAPH_THEME: GraphTheme = {
	label: COLORS.stone100,
	inactive: COLORS.stone400,
	edge: COLORS.stone800,
	node: {
		focus: {
			selected: COLORS.sky400,
			parent: COLORS.blue400,
			child: COLORS.amber400
		},
		levels: [
			COLORS.cyan800,
			COLORS.cyan700,
			COLORS.cyan600,
			COLORS.cyan500,
			COLORS.cyan400,
			COLORS.cyan300
		]
	}
}

export const BASE_NODE_SIZE = 6
export const NODE_SIZE_MULTIPLIER = 2
export const ACTIVE_EDGE_SIZE = 3
