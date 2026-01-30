import { getCssVar } from '$lib/utils/theme';

// Color configuration interface
interface ThemeColors {
    inactive: string;
    node: {
        focus: {
            selected: string;
            parent: string;
            child: string;
        };
        levels: string[];
    };
}

// Default/fallback colors
const FALLBACK: ThemeColors = {
    inactive: '#64748b',
    node: {
        focus: {
            selected: '#38bdf8', // sky-400
            parent: '#60a5fa', // blue-400
            child: '#fbbf24'   // amber-400
        },
        levels: [
            '#155e75', // cyan-800
            '#0e7490', // cyan-700
            '#0891b2', // cyan-600
            '#06b6d4', // cyan-500
            '#22d3ee', // cyan-400
            '#67e8f9', // cyan-300
        ]
    }
};

// For legend display (uses fallback colors)
export const COLORS = FALLBACK;

// Resolve colors from CSS vars (no caching - always fresh)
export const getThemeColors = (): ThemeColors => {
    const css = (v: string, fallback: string) => getCssVar(v) || fallback;
    return {
        inactive: css('--color-muted', FALLBACK.inactive),
        node: {
            focus: {
                selected: css('--color-accent', FALLBACK.node.focus.selected),
                parent: css('--color-info', FALLBACK.node.focus.parent),
                child: css('--color-warn', FALLBACK.node.focus.child)
            },
            levels: FALLBACK.node.levels.map((fallback, i) => css(`--color-lvl${i}`, fallback))
        }
    };
};

export const BASE_NODE_SIZE = 6;
export const NODE_SIZE_MULTIPLIER = 2;
export const ACTIVE_EDGE_SIZE = 3;
