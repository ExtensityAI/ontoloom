<script lang="ts">
	import Markdown from './Markdown.svelte'

	let {
		title,
		content,
		color
	}: {
		title: string
		content: string | null | undefined
		color: 'info' | 'warn' | 'ok' | 'err'
	} = $props()
</script>

<section class="border-l-2 border-{color} pl-4">
	<h2 class="mb-3 text-xs font-semibold uppercase tracking-wide text-{color}">{title}</h2>
	<div class="text-sm">
		{#if content}
			<Markdown {content} />
		{:else}
			<p class="text-muted">No {title.toLowerCase()} for this iteration</p>
		{/if}
	</div>
</section>
