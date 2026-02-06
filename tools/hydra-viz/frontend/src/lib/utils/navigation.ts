export const getRunPath = (name: string): string => `/runs/${encodeURIComponent(name)}`

export const getIterationPath = (name: string, iter: number | string): string =>
	`${getRunPath(name)}/${iter}`
