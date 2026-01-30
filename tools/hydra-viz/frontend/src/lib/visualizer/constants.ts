import { getVisualizerTheme, type VisualizerThemeColors } from '$lib/utils/theme'

export type { VisualizerThemeColors as ThemeColors }

/** Get theme colors from CSS variables */
export const getThemeColors = getVisualizerTheme

export const BASE_NODE_SIZE = 6
export const NODE_SIZE_MULTIPLIER = 2
export const ACTIVE_EDGE_SIZE = 3
