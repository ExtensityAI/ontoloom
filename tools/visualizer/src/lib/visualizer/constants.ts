export const LEVEL_COLORS = [
    "#ec003f", // rose-500 (root)
    "#fd9a00", // amber-500
    "#7ccf00", // lime-500
    "#22c55e", // green-500
    "#14b8a6", // teal-500
    "#3b82f6", // blue-500
    "#8b5cf6", // violet-500
    "#ec4899", // pink-500
    "#64748b", // slate-500
] as const

export const COLORS = {
    node: {
        inactive: "#e5e5e5",
        selected: "#dc2626", // red
        parent: "#f97316", // orange
        child: "#22c55e", // green
    },
    edge: {
        hierarchy: {
            default: "#e5e5e5",
            active: "#a3a3a3",
            inactive: "#f5f5f5",
        },
        property: {
            default: "#f87171",
            active: "#dc2626",
            inactive: "#fecaca",
        },
    },
} as const

export const BASE_NODE_SIZE = 8
export const NODE_SIZE_MULTIPLIER = 4
export const ACTIVE_EDGE_SIZE = 3
