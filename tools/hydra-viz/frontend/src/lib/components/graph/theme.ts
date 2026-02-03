import { formatHex, parse } from "culori"
import colors from "tailwindcss/colors"

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

const hexify = <T>(value: T): T => {
  if (typeof value === "string") return formatHex(parse(value))! as T
  if (Array.isArray(value)) return value.map(hexify) as T
  if (typeof value === "object" && value !== null) {
    return Object.fromEntries(Object.entries(value).map(([k, v]) => [k, hexify(v)])) as T
  }
  return value
}

export const graphTheme: GraphTheme = hexify({
  label: colors.stone[100],
  inactive: colors.stone[400],
  edge: colors.stone[800],
  node: {
    focus: {
      selected: colors.green[500],
      parent: colors.sky[500],
      child: colors.amber[500]
    },
    levels: [colors.stone[200], colors.stone[300], colors.stone[400], colors.stone[500]]
  }
})

console.log(graphTheme)

export const baseNodeSize = 6
export const nodeSizeMultiplier = 2
export const activeEdgeSize = 3
