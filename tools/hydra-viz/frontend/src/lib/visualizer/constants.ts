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
    diff: {
        added: string;
        removed: string;
        modified: string;
    };
}

// Default colors (also used for SSR) - cyan gradient for depth
export const COLORS: ThemeColors = {
    inactive: '#64748b',
    node: {
        focus: {
            selected: '#f472b6',
            parent: '#831843',
            child: '#fce7f3'
        },
        // Cyan gradient: dark (root) to light (leaves)
        levels: [
            '#0e7490', // cyan-700 - root
            '#0891b2', // cyan-600
            '#06b6d4', // cyan-500
            '#22d3ee', // cyan-400
            '#67e8f9', // cyan-300
            '#a5f3fc', // cyan-200
            '#cffafe', // cyan-100
            '#ecfeff', // cyan-50
            '#f0fdfa'  // teal-50 - very deep fallback
        ]
    },
    diff: {
        added: '#22c55e',
        removed: '#ef4444',
        modified: '#f59e0b'
    }
};

// Resolve colors from CSS vars (cached)
let _resolved: ThemeColors | null = null;

export const getThemeColors = (): ThemeColors => {
    if (_resolved) return _resolved;

    const css = (v: string, fallback: string) => getCssVar(v) || fallback;
    _resolved = {
        inactive: css('--color-focus-inactive', COLORS.inactive),
        node: {
            focus: {
                selected: css('--color-focus-selected', COLORS.node.focus.selected),
                parent: css('--color-focus-parent', COLORS.node.focus.parent),
                child: css('--color-focus-child', COLORS.node.focus.child)
            },
            levels: COLORS.node.levels.map((fallback, i) => css(`--color-lvl${i}`, fallback))
        },
        diff: {
            added: css('--color-diff-added', COLORS.diff.added),
            removed: css('--color-diff-removed', COLORS.diff.removed),
            modified: css('--color-diff-modified', COLORS.diff.modified)
        }
    };
    return _resolved;
};

// Clear cached colors (useful when theme changes)
export const clearThemeCache = () => {
    _resolved = null;
};

export const BASE_NODE_SIZE = 6;
export const NODE_SIZE_MULTIPLIER = 2;
export const ACTIVE_EDGE_SIZE = 3;
