
export const COLORS = {
    inactive: "#f5f5f5", // neutral-100
    node: {
        focus: {
            selected: "#f43f5e", // rose-500
            parent: "#4c0519", // rose-950
            child: "#fecdd3", // rose-200
        },
        levels: [
            "#f43f5e", // rose-500 (root)
            "#f59e0b", // amber-500
            "#84cc16", // lime-500
            "#22c55e", // green-500
            "#14b8a6", // teal-500
            "#3b82f6", // blue-500
            "#8b5cf6", // violet-500
            "#ec4899", // pink-500
            "#64748b", // slate-500
    ]

    },
} as const

export const BASE_NODE_SIZE = 6
export const NODE_SIZE_MULTIPLIER = 2
export const ACTIVE_EDGE_SIZE = 3
