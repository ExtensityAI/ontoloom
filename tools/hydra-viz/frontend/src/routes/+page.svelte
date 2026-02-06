<script lang="ts">
  import { formatDateTime } from "$lib/utils/date"
  import type { PageData } from "./$types"

  let { data }: { data: PageData } = $props()

  const sortedRuns = $derived(
    data.runs.toSorted(
      (a, b) =>
        new Date(b.metadata.created_at).getTime() - new Date(a.metadata.created_at).getTime()
    )
  )
</script>

<div class="flex-1 overflow-auto px-4 py-8">
  <div class="mx-auto w-full max-w-4xl">
    {#if sortedRuns.length === 0}
      <p class="text-muted">No runs found</p>
    {:else}
      <ul class="divide-y divide-edge border border-edge">
        {#each sortedRuns as run}
          <li>
            <a
              href={`/runs/${run.metadata.id}`}
              class="group flex items-center gap-8 px-4 py-2 text-faint transition hover:bg-surface"
            >
              <div class="font-mono transition group-hover:text-fg">{run.metadata.id}</div>
              <div class="grow text-xs">{run.metadata.title}</div>

              <time datetime={run.metadata.created_at} class="font-mono text-xs">
                {formatDateTime(run.metadata.created_at)}
              </time></a
            >
          </li>
        {/each}
      </ul>
    {/if}
  </div>
</div>
