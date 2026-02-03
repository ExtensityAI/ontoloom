<script lang="ts">
  import { formatDateTimeFull } from "$lib/utils/date"
  import type { PageData } from "./$types"

  let { data }: { data: PageData } = $props()

  const runs = $derived(data.runs)
  const sortedRuns = $derived(
    runs.toSorted(
      (a, b) =>
        new Date(b.metadata.created_at).getTime() - new Date(a.metadata.created_at).getTime()
    )
  )
  const runCount = $derived(sortedRuns.length)

  const link = "text-faint hover:text-fg transition-colors"
</script>

<main class="flex-1 overflow-auto px-4 py-8">
  <div class="mx-auto w-full max-w-4xl">
    {#if runCount === 0}
      <p class="text-muted">No runs found</p>
    {:else}
      <ul class="divide-y divide-edge border border-edge">
        {#each sortedRuns as run}
          <li>
            <a href={`/runs/${run.metadata.id}`} class="flex items-center gap-8 px-4 py-2 {link}">
              <div class="font-mono">{run.metadata.id}</div>
              <div class="grow text-xs">{run.metadata.title}</div>

              <time datetime={run.metadata.created_at} class="font-mono text-xs text-faint">
                {formatDateTimeFull(run.metadata.created_at)}
              </time></a
            >
          </li>
        {/each}
      </ul>
    {/if}
  </div>
</main>
