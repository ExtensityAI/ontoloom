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

	const accentClass = {
		info: 'bg-info',
		warn: 'bg-warn',
		ok: 'bg-ok',
		err: 'bg-err'
	}[color]
</script>

<section class="relative overflow-hidden rounded border border-edge bg-surface/30 p-3">
	<div class={`absolute inset-x-0 top-0 h-0.5 ${accentClass}`}></div>
	<h2 class="mb-3 text-sm font-medium text-muted">{title}</h2>
	<div class="text-sm">
		{#if content}
			<Markdown {content} />
		{:else}
			<p class="text-muted">No {title.toLowerCase()} for this iteration</p>
		{/if}
	</div>
</section>
