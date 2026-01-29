<script lang="ts">
	import { COLORS } from '$lib/visualizer/constants';
	import type { OntologyDiff } from '$lib/utils/diff';
	import { hasDiffChanges } from '$lib/utils/diff';

	let { maxLevel = 5, diff }: { maxLevel?: number; diff?: OntologyDiff } = $props();

	const levels = COLORS.node.levels.slice(0, Math.min(maxLevel + 1, COLORS.node.levels.length));
	const showDiff = $derived(diff && hasDiffChanges(diff));
</script>

<div class="rounded-lg border border-edge bg-surface p-3 text-sm">
	<div class="mb-2 font-semibold text-muted">Legend</div>

	<!-- Depth gradient -->
	<div class="mb-3">
		<div class="mb-1 text-faint">Hierarchy Depth</div>
		<div class="flex items-center gap-1">
			<span class="text-faint">Root</span>
			<div class="flex h-3 flex-1 overflow-hidden rounded">
				{#each levels as color}
					<div class="flex-1" style="background-color: {color}"></div>
				{/each}
			</div>
			<span class="text-faint">Leaf</span>
		</div>
	</div>

	<!-- Node size -->
	<div class="mb-3">
		<div class="mb-1 text-faint">Node Size</div>
		<div class="flex items-center gap-2">
			<div class="h-4 w-4 rounded-full bg-lvl0"></div>
			<span class="text-muted">Larger = closer to root</span>
		</div>
	</div>

	<!-- Edge types -->
	<div class="mb-3">
		<div class="mb-1 text-faint">Edge Types</div>
		<div class="space-y-1">
			<div class="flex items-center gap-2">
				<div class="h-0.5 w-6 bg-muted"></div>
				<span class="text-muted">isA (hierarchy)</span>
			</div>
			<div class="flex items-center gap-2">
				<div class="h-0.5 w-6 border-t border-dashed border-muted bg-muted/50"></div>
				<span class="text-muted">Object property</span>
			</div>
		</div>
	</div>

	<!-- Diff legend (only shown when diff is present) -->
	{#if showDiff}
		<div>
			<div class="mb-1 text-faint">Changes</div>
			<div class="space-y-1">
				<div class="flex items-center gap-2">
					<div class="h-3 w-3 rounded-full border-2" style="border-color: {COLORS.diff.added}"></div>
					<span class="text-muted">Added</span>
				</div>
				<div class="flex items-center gap-2">
					<div class="h-3 w-3 rounded-full" style="background-color: {COLORS.diff.removed}"></div>
					<span class="text-muted">Removed</span>
				</div>
				<div class="flex items-center gap-2">
					<div class="h-3 w-3 rounded-full border-2" style="border-color: {COLORS.diff.modified}"></div>
					<span class="text-muted">Modified</span>
				</div>
			</div>
		</div>
	{/if}
</div>
