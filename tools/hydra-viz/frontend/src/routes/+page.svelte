<script lang="ts">
  import Header from "$lib/components/layout/Header.svelte"
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
</script>

<div class="flex h-full flex-col text-sm">
  <!-- Header -->
  <Header>
    <h1 class="">ontology-hydra</h1>
    <div class="flex-1"></div>
    <div class="text-sm text-muted">{runCount} runs</div>
  </Header>

  <!-- Content -->
  <main class="flex-1 overflow-auto">
    <div class="mx-auto w-full max-w-3xl p-6">
      <h2 class="mb-4 text-lg font-semibold text-fg">Runs</h2>

      {#if runCount === 0}
        <p class="text-muted">No runs found</p>
      {:else}
        <div class="border border-edge">
          <ul class="divide-y divide-edge">
            {#each sortedRuns as run}
              <li>
                <a
                  href={`/runs/${run.metadata.name}`}
                  class="group flex items-center justify-between gap-4 px-4 py-3 text-fg transition-colors duration-150 hover:bg-fg hover:text-bg"
                >
                  <span class="font-mono group-hover:text-bg">{run.metadata.name}</span>
                  <span class="font-mono text-sm text-muted group-hover:text-bg">
                    {formatDateTimeFull(run.metadata.created_at)}
                  </span>
                </a>
              </li>
            {/each}
          </ul>
        </div>
      {/if}
    </div>
  </main>
</div>
