<script lang="ts">
	import { page } from '$app/state'
	import { getRunPath, getIterationPath } from '$lib/utils/navigation'

	interface Crumb { label: string; href?: string }

	const crumbs = $derived.by((): Crumb[] => {
		const { name, iter } = page.params
		if (!name) return [{ label: 'runs' }]
		if (!iter) return [{ label: 'runs', href: '/' }, { label: name }]

		const routeParts = (page.route.id ?? '').split('/')
		const subpage = routeParts.length > 4 ? routeParts[4] : null

		const result: Crumb[] = [
			{ label: 'runs', href: '/' },
			{ label: name, href: getRunPath(name) }
		]
		if (subpage) {
			result.push({ label: 'iter ' + iter, href: getIterationPath(name, iter) })
			result.push({ label: subpage })
		} else {
			result.push({ label: 'iter ' + iter })
		}
		return result
	})
</script>

<nav class="flex items-center">
	{#each crumbs as crumb, i}
		{#if i > 0}
			<span class="text-faint">/</span>
		{/if}
		{#if crumb.href}
			<a href={crumb.href} class="px-2 py-1 text-faint transition-colors hover:text-fg">
				{crumb.label}
			</a>
		{:else}
			<span class="px-2 py-1 text-fg">{crumb.label}</span>
		{/if}
	{/each}
</nav>
