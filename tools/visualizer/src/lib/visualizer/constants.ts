
export const COLORS = {
    inactive: "#e7e5e4", // stone-200
    node: {
        focus: {
            selected: "#e11d48", // rose-600
            parent: "#4c0519", // rose-950
            child: "#fda4af", // rose-300
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
    edge: {
        hierarchy: {
            default: "#d6d3d1", // stone-300
            active: "#a3a3a3", // stone-400
        },
        property: {
            default: "#d6d3d1", // stone-300
            active: "#a3a3a3", // stone-400
        },
    },
} as const

export const BASE_NODE_SIZE = 8
export const NODE_SIZE_MULTIPLIER = 4
export const ACTIVE_EDGE_SIZE = 3
