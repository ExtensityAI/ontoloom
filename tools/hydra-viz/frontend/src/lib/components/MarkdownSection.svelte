<script lang="ts">
	import Markdown from '$lib/components/Markdown.svelte'

	let {
		title,
		content,
		color
	}: {
		title: string
		content: string | null | undefined
		color: 'info' | 'warn' | 'ok' | 'err'
	} = $props()

	const borderClass = $derived(
		color === 'info'
			? 'border-info'
			: color === 'warn'
				? 'border-warn'
				: color === 'ok'
					? 'border-ok'
					: 'border-err'
	)

	const textClass = $derived(
		color === 'info'
			? 'text-info'
			: color === 'warn'
				? 'text-warn'
				: color === 'ok'
					? 'text-ok'
					: 'text-err'
	)
</script>

<section class="border-l-2 {borderClass} pl-4">
	<h2 class="mb-3 text-xs font-semibold uppercase tracking-wide {textClass}">{title}</h2>
	<div class="text-sm">
		{#if content}
			<Markdown {content} />
		{:else}
			<p class="text-muted">No {title.toLowerCase()} for this iteration</p>
		{/if}
	</div>
</section>
