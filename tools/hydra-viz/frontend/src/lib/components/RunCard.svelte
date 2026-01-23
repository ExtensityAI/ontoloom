<script lang="ts">
	import type { RunSummary } from '$lib/api/types';
	import { formatRelativeTime } from '$lib/utils/date';
	import { ClockIcon, LayersIcon, FileIcon, CheckCircleIcon, LoaderIcon } from '@lucide/svelte';

	let { run }: { run: RunSummary } = $props();

	const relativeTime = $derived(formatRelativeTime(run.metadata.created_at));

	// Determine status based on iteration count (simple heuristic)
	const isComplete = $derived(run.metadata.n_iterations >= 1);
</script>

<a
	href="/runs/{encodeURIComponent(run.metadata.name)}"
	class="block bg-surface border border-edge rounded-lg p-5 hover:bg-hover hover:border-muted/30 transition-all card-shadow hover:card-shadow-lg group"
>
	<div class="flex items-start justify-between gap-4">
		<div class="flex-1 min-w-0">
			<!-- Run name -->
			<div class="flex items-center gap-2">
				<div
					class="text-lg font-semibold truncate group-hover:text-accent transition-colors"
					title={run.metadata.name}
				>
					{run.metadata.name}
				</div>
				{#if isComplete}
					<CheckCircleIcon class="w-4 h-4 text-ok shrink-0" />
				{:else}
					<LoaderIcon class="w-4 h-4 text-warn shrink-0 animate-spin" />
				{/if}
			</div>

			<!-- Relative time -->
			<div class="flex items-center gap-1.5 text-sm text-muted mt-1">
				<ClockIcon class="w-3.5 h-3.5" />
				<span>{relativeTime}</span>
			</div>

			<!-- Stats row -->
			<div class="flex items-center gap-4 mt-3 text-sm">
				<div class="flex items-center gap-1.5 text-faint">
					<LayersIcon class="w-3.5 h-3.5" />
					<span>
						{run.metadata.n_iterations} iteration{run.metadata.n_iterations !== 1 ? 's' : ''}
					</span>
				</div>
				<div class="flex items-center gap-1.5 text-faint">
					<FileIcon class="w-3.5 h-3.5" />
					<span>
						{run.metadata.input_files.length} file{run.metadata.input_files.length !== 1 ? 's' : ''}
					</span>
				</div>
			</div>

			<!-- Intent preview -->
			{#if run.metadata.intent}
				<div class="text-sm text-faint mt-3 line-clamp-2" title={run.metadata.intent}>
					{run.metadata.intent}
				</div>
			{/if}
		</div>
	</div>
</a>
