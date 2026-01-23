<script lang="ts">
	import { ChevronLeftIcon, ChevronRightIcon } from '@lucide/svelte';

	let {
		current = $bindable(0),
		max,
		onchange
	}: {
		current: number;
		max: number;
		onchange?: (value: number) => void;
	} = $props();

	const prev = () => {
		if (current > 0) {
			current--;
			onchange?.(current);
		}
	};

	const next = () => {
		if (current < max) {
			current++;
			onchange?.(current);
		}
	};

	const handleInput = (e: Event) => {
		const target = e.target as HTMLInputElement;
		current = parseInt(target.value, 10);
		onchange?.(current);
	};
</script>

<div class="flex items-center gap-4 bg-surface rounded-lg px-4 py-2 border border-edge">
	<span class="text-sm text-muted">Iteration</span>

	<button
		type="button"
		onclick={prev}
		disabled={current === 0}
		class="p-1 rounded hover:bg-hover disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
	>
		<ChevronLeftIcon class="w-5 h-5" />
	</button>

	<input type="range" min="0" {max} value={current} oninput={handleInput} class="flex-1" />

	<button
		type="button"
		onclick={next}
		disabled={current === max}
		class="p-1 rounded hover:bg-hover disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
	>
		<ChevronRightIcon class="w-5 h-5" />
	</button>

	<span class="text-sm font-mono min-w-[4ch] text-right">{current}/{max}</span>
</div>
