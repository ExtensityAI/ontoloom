/** Resolve a CSS custom property value at runtime */
export const getCssVar = (name: string): string =>
	getComputedStyle(document.documentElement).getPropertyValue(name).trim();

