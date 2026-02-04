export type Crumb = { label: string; href?: string }

/** Build the path to a run page */
export const getRunPath = (name: string): string => `/runs/${encodeURIComponent(name)}`

/** Build the path to an iteration page */
export const getIterationPath = (name: string, iter: number | string): string =>
  `${getRunPath(name)}/${iter}`

/** Build breadcrumbs for the runs list page */
export const getRunsListCrumbs = (): Crumb[] => [{ label: "runs" }]

/** Build breadcrumbs for a run overview page */
export const getRunCrumbs = (name: string): Crumb[] => [
  { label: "runs", href: "/" },
  { label: name }
]

/** Build breadcrumbs for an iteration page */
export const getIterationCrumbs = (name: string, iter: string): Crumb[] => [
  { label: "runs", href: "/" },
  { label: name, href: getRunPath(name) },
  { label: "iter " + iter }
]

/** Build breadcrumbs for a sub-page within an iteration (graph, changes) */
export const getIterationSubpageCrumbs = (name: string, iter: string, subpage: string): Crumb[] => [
  { label: "runs", href: "/" },
  { label: name, href: getRunPath(name) },
  { label: "iter " + iter, href: getIterationPath(name, iter) },
  { label: subpage }
]
