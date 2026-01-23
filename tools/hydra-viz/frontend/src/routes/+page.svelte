<script lang="ts">
	import { formatDateTimeFull } from '$lib/utils/date';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	const runs = $derived(data.runs);

	// Sort runs by date (most recent first)
	const sortedRuns = $derived(
		runs.toSorted(
			(a, b) =>
				new Date(b.metadata.created_at).getTime() - new Date(a.metadata.created_at).getTime()
		)
	);
</script>

<main>
	<ul>
		{#each sortedRuns as run}
			<li class="border-t border-neutral-800 py-4 first:border-t-0">
				<a class="group block" href={`/runs/${run.metadata.name}`}
					><div>
						<div class="text-lg transition group-hover:text-lime-300">{run.metadata.name}</div>
						<time datetime={run.metadata.created_at} class="font-mono text-xs text-neutral-600">
							{formatDateTimeFull(run.metadata.created_at)}
						</time>
					</div></a
				>
			</li>
		{/each}
	</ul>
</main>
