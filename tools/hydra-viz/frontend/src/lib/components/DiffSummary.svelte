<script lang="ts">
	import type { OntologyDiff } from '$lib/utils/diff';
	import { getDiffCounts, hasDiffChanges } from '$lib/utils/diff';
	import { PlusIcon, MinusIcon, PencilIcon } from '@lucide/svelte';

	let {
		diff,
		previousIteration,
		currentIteration
	}: {
		diff: OntologyDiff;
		previousIteration: number;
		currentIteration: number;
	} = $props();

	const counts = $derived(getDiffCounts(diff));
	const hasChanges = $derived(hasDiffChanges(diff));

	// Total changes across all categories
	const totalAdded = $derived(
		counts.classes.added + counts.dataProperties.added + counts.objectProperties.added
	);
	const totalRemoved = $derived(
		counts.classes.removed + counts.dataProperties.removed + counts.objectProperties.removed
	);
	const totalModified = $derived(
		counts.classes.modified + counts.dataProperties.modified + counts.objectProperties.modified
	);
</script>

{#if hasChanges}
	<div class="flex items-center gap-4 bg-surface rounded-lg px-4 py-2 border border-edge text-sm">
		<span class="text-muted">
			Changes from iteration {previousIteration} → {currentIteration}:
		</span>

		<div class="flex items-center gap-3">
			{#if totalAdded > 0}
				<div class="flex items-center gap-1 text-ok">
					<PlusIcon class="w-4 h-4" />
					<span>{totalAdded}</span>
					{#if counts.classes.added > 0}
						<span class="text-xs text-muted">
							({counts.classes.added} class{counts.classes.added !== 1 ? 'es' : ''})
						</span>
					{/if}
				</div>
			{/if}

			{#if totalRemoved > 0}
				<div class="flex items-center gap-1 text-err">
					<MinusIcon class="w-4 h-4" />
					<span>{totalRemoved}</span>
					{#if counts.classes.removed > 0}
						<span class="text-xs text-muted">
							({counts.classes.removed} class{counts.classes.removed !== 1 ? 'es' : ''})
						</span>
					{/if}
				</div>
			{/if}

			{#if totalModified > 0}
				<div class="flex items-center gap-1 text-warn">
					<PencilIcon class="w-4 h-4" />
					<span>{totalModified}</span>
					{#if counts.classes.modified > 0}
						<span class="text-xs text-muted">
							({counts.classes.modified} class{counts.classes.modified !== 1 ? 'es' : ''})
						</span>
					{/if}
				</div>
			{/if}
		</div>

		<!-- Detailed breakdown on hover -->
		<div class="ml-auto text-xs text-faint">
			{#if counts.dataProperties.total > 0}
				<span>{counts.dataProperties.total} data prop{counts.dataProperties.total !== 1 ? 's' : ''}</span>
			{/if}
			{#if counts.objectProperties.total > 0}
				<span class="ml-2">{counts.objectProperties.total} obj prop{counts.objectProperties.total !== 1 ? 's' : ''}</span>
			{/if}
		</div>
	</div>
{/if}
