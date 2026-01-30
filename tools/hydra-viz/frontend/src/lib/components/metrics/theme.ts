/** Resolve a CSS custom property value at runtime */
const getCssVar = (name: string): string =>
	getComputedStyle(document.documentElement).getPropertyValue(name).trim()

/** Theme colors for charts */
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

/** Get chart theme colors from CSS variables */
export const getChartTheme = (): ChartTheme => ({
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
