<script lang="ts">
	import { formatDelta, getDeltaClass } from '$lib/utils/delta'

	let {
		value,
		label,
		current,
		previous,
		invert = false,
		size = 'default'
	}: {
		value: string | number
		label: string
		current?: number
		previous?: number
		invert?: boolean
		size?: 'default' | 'small'
	} = $props()

	const delta = $derived(formatDelta(current, previous))
	const deltaClass = $derived(getDeltaClass(current, previous, invert))
	const valueClass = $derived(size === 'small' ? 'text-xl' : 'text-2xl')
</script>

<div class="border border-edge p-4">
	<div class="{valueClass} font-semibold text-fg">{value}</div>
	<div class="mt-1 flex items-center gap-2 text-sm">
		<span class="text-muted">{label}</span>
		{#if delta}
			<span class={deltaClass}>{delta}</span>
		{/if}
	</div>
</div>
