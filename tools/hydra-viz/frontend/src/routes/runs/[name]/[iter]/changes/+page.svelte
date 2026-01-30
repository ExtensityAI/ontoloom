<script lang="ts">
	import MarkdownSection from '$lib/components/MarkdownSection.svelte'
	import {
		groupOperations,
		getOperationDisplayName,
		getOperationBadgeClass
	} from '$lib/utils/operations'
	import type { PageData } from './$types'

	let { data }: { data: PageData } = $props()

	const iteration = $derived(data.iteration)
	const groupedOps = $derived(groupOperations(iteration?.ops ?? []))

	// TODO: Replace with actual attempts data when available
	const attempts = [{ id: 1, status: 'success' as const }]
	let selectedAttempt = $state(1)
	const hasMultipleAttempts = $derived(attempts.length > 1)
</script>

<div class="mx-auto w-full max-w-6xl space-y-12 px-4 py-8">
	{#if hasMultipleAttempts}
		<div class="flex items-center gap-2 font-mono text-sm">
			<span class="text-faint">attempt:</span>
			{#each attempts as attempt}
				<button
					class="px-2 py-1 transition-colors duration-150
            {selectedAttempt === attempt.id
						? 'bg-fg text-bg'
						: 'text-muted hover:bg-fg hover:text-bg'}"
					onclick={() => (selectedAttempt = attempt.id)}
				>
					{attempt.id}
					{#if attempt.status === 'success'}
						<span class="text-ok">✓</span>
					{:else if attempt.status === 'rejected'}
						<span class="text-err">✗</span>
					{/if}
				</button>
			{/each}
		</div>
	{/if}

	<MarkdownSection title="Plan" content={iteration?.plan} color="info" />

	<section class="border-l-2 border-warn pl-4">
		<div class="mb-3 flex items-center gap-4">
			<h2 class="text-xs font-semibold uppercase tracking-wide text-warn">Operations</h2>
			{#if iteration?.ops?.length}
				<div class="flex gap-3 text-xs">
					{#if groupedOps.adds.length}
						<span class="text-ok">{groupedOps.adds.length} added</span>
					{/if}
					{#if groupedOps.updates.length}
						<span class="text-warn">{groupedOps.updates.length} updated</span>
					{/if}
					{#if groupedOps.deletes.length}
						<span class="text-err">{groupedOps.deletes.length} deleted</span>
					{/if}
					{#if groupedOps.merges.length}
						<span class="text-info">{groupedOps.merges.length} merged</span>
					{/if}
				</div>
			{/if}
		</div>

		<div class="border border-edge">
			{#if iteration?.ops?.length}
				<ul class="divide-y divide-edge">
					{#each iteration.ops as op}
						<li class="flex items-center gap-3 px-4 py-3">
							<span
								class="shrink-0 border px-2 py-0.5 font-mono text-sm {getOperationBadgeClass(
									op.op
								)}"
							>
								{op.op}
							</span>
							<span class="text-sm text-fg">{getOperationDisplayName(op)}</span>
						</li>
					{/each}
				</ul>
			{:else}
				<p class="p-4 text-muted">No operations in this iteration</p>
			{/if}
		</div>
	</section>

	<MarkdownSection title="Review" content={iteration?.review} color="ok" />
</div>
