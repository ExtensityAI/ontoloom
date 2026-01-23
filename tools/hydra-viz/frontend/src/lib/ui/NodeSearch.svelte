<script lang="ts">
	import { onMount } from 'svelte';
	import type { HydraGraph } from '$lib/graph/types';

	const MAX_RESULTS = 200;

	let {
		onSelect,
		graph
	}: { onSelect: (nodeId: string) => void; graph: HydraGraph } = $props();

	let input!: HTMLInputElement;
	let query = $state('');
	let activeIndex = $state(0);
	let listElement: HTMLDivElement | null = $state(null);

	const moveSelection = (delta: number) => {
		if (!listElement) return;
		if (results.length === 0) return;

		activeIndex = Math.max(0, (activeIndex + delta) % results.length);
		listElement.children.item(activeIndex)?.scrollIntoView({ block: 'nearest' });
	};

	const results = $derived.by(() => {
		const q = query.trim().toLowerCase();
		const nodes = graph.nodes();

		if (!q) return nodes.slice(0, MAX_RESULTS);

		const startsWith: string[] = [];
		const includes: string[] = [];

		for (const node of nodes) {
			const lower = node.toLowerCase();
			if (lower.startsWith(q)) startsWith.push(node);
			else if (lower.includes(q)) includes.push(node);
		}

		const matches = [...startsWith, ...includes];
		return matches.slice(0, MAX_RESULTS);
	});

	const onKeyDown = (e: KeyboardEvent) => {
		if (e.key === 'ArrowDown') {
			if (results.length === 0) return;
			e.preventDefault();
			moveSelection(1);
			return;
		}

		if (e.key === 'ArrowUp') {
			if (results.length === 0) return;
			e.preventDefault();
			moveSelection(-1);
			return;
		}

		if (e.key !== 'Enter') return;

		activeIndex = 0;

		const nodeId = results[activeIndex];
		if (nodeId) onSelect(nodeId);
	};

	onMount(() => {
		input.focus();
	});
</script>

<div class="bg-surface/90 backdrop-blur-md border border-edge rounded-lg w-80 shadow-lg">
	<input
		bind:this={input}
		bind:value={query}
		type="text"
		placeholder="Search for node..."
		class="px-4 py-2 rounded-t-lg w-full bg-transparent placeholder-faint border-b border-edge focus:outline-none focus:ring-1 focus:ring-accent"
		onkeydown={onKeyDown}
	/>

	<div class="max-h-72 overflow-y-auto rounded-b-lg" bind:this={listElement}>
		{#each results as option, i}
			<button
				type="button"
				class="px-4 py-2 cursor-pointer block w-full text-left text-sm text-muted hover:bg-hover {activeIndex ===
				i
					? 'bg-hover text-fg font-medium'
					: ''}"
				onclick={() => onSelect(option)}
				onmouseenter={() => (activeIndex = i)}
			>
				{option}
			</button>
		{/each}
		{#if results.length === 0}
			<div class="px-4 py-3 text-sm text-faint">No results found</div>
		{/if}
	</div>
</div>
