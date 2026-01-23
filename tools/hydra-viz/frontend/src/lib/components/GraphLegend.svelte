<script lang="ts">
	import { COLORS } from '$lib/visualizer/constants';
	import type { OntologyDiff } from '$lib/utils/diff';
	import { hasDiffChanges } from '$lib/utils/diff';

	let { maxLevel = 5, diff }: { maxLevel?: number; diff?: OntologyDiff } = $props();

	const levels = COLORS.node.levels.slice(0, Math.min(maxLevel + 1, COLORS.node.levels.length));
	const showDiff = $derived(diff && hasDiffChanges(diff));
</script>

<div class="bg-surface/90 backdrop-blur-sm rounded-lg border border-edge p-3 text-xs">
	<div class="font-semibold text-muted mb-2">Legend</div>

	<!-- Depth gradient -->
	<div class="mb-3">
		<div class="text-faint mb-1">Hierarchy Depth</div>
		<div class="flex items-center gap-1">
			<span class="text-faint">Root</span>
			<div class="flex-1 flex h-3 rounded overflow-hidden">
				{#each levels as color}
					<div class="flex-1" style="background-color: {color}"></div>
				{/each}
			</div>
			<span class="text-faint">Leaf</span>
		</div>
	</div>

	<!-- Node size -->
	<div class="mb-3">
		<div class="text-faint mb-1">Node Size</div>
		<div class="flex items-center gap-2">
			<div class="w-4 h-4 rounded-full bg-lvl0"></div>
			<span class="text-muted">Larger = closer to root</span>
		</div>
	</div>

	<!-- Edge types -->
	<div class="mb-3">
		<div class="text-faint mb-1">Edge Types</div>
		<div class="space-y-1">
			<div class="flex items-center gap-2">
				<div class="w-6 h-0.5 bg-muted"></div>
				<span class="text-muted">isA (hierarchy)</span>
			</div>
			<div class="flex items-center gap-2">
				<div class="w-6 h-0.5 bg-muted/50 border-t border-dashed border-muted"></div>
				<span class="text-muted">Object property</span>
			</div>
		</div>
	</div>

	<!-- Diff legend (only shown when diff is present) -->
	{#if showDiff}
		<div>
			<div class="text-faint mb-1">Changes</div>
			<div class="space-y-1">
				<div class="flex items-center gap-2">
					<div class="w-3 h-3 rounded-full border-2" style="border-color: {COLORS.diff.added}"></div>
					<span class="text-muted">Added</span>
				</div>
				<div class="flex items-center gap-2">
					<div class="w-3 h-3 rounded-full" style="background-color: {COLORS.diff.removed}"></div>
					<span class="text-muted">Removed</span>
				</div>
				<div class="flex items-center gap-2">
					<div class="w-3 h-3 rounded-full border-2" style="border-color: {COLORS.diff.modified}"></div>
					<span class="text-muted">Modified</span>
				</div>
			</div>
		</div>
	{/if}
</div>
