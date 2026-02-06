<script lang="ts">
	import { computeDelta } from '$lib/utils/delta'

	let {
		value,
		label,
		current,
		previous
	}: {
		value: string | number
		label: string
		current?: number
		previous?: number
	} = $props()

	const effectiveCurrent = $derived(current ?? (typeof value === 'number' ? value : undefined))
	const delta = $derived(computeDelta(effectiveCurrent, previous))
</script>

<div class="border border-edge p-4">
	<div class="text-2xl font-semibold text-fg">{value}</div>
	<div class="mt-1 flex items-center gap-2 text-sm">
		<span class="text-muted">{label}</span>
		{#if delta.text}
			<span class={delta.color}>{delta.text}</span>
		{/if}
	</div>
</div>
