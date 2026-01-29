<script lang="ts">
  import { page } from "$app/stores"
  import Header from "$lib/components/layout/Header.svelte"
  import { ChevronRightIcon } from "@lucide/svelte"
  import type { Snippet } from "svelte"
  import type { LayoutData } from "./$types"

  let { data, children }: { data: LayoutData; children: Snippet } = $props()

  const run = $derived(data.run)
  const name = $derived($page.params.name)

  const hasIter = $derived($page.params.iter !== undefined)
  const currentIter = $derived(parseInt($page.params.iter ?? "-1", 10))
  const currentSubView = $derived.by(() => {
    if (!hasIter) return null
    const pathParts = $page.url.pathname.split("/").filter(Boolean)
    const last = pathParts[pathParts.length - 1]
    if (!isNaN(parseInt(last, 10))) return "metrics"
    return last
  })

  let expandedIters = $state<Set<number>>(new Set())

  const toggleIter = (idx: number) => {
    const next = new Set(expandedIters)
    if (next.has(idx)) {
      next.delete(idx)
    } else {
      next.add(idx)
    }
    expandedIters = next
  }

  const isIterViewActive = (idx: number, view: string) => {
    return hasIter && currentIter === idx && currentSubView === view
  }
</script>

<!-- Header -->
<Header>
  <a href="/" class="text-muted transition hover:text-fg">runs</a>
  <span class="text-faint">/</span>
  <span class="text-fg">{name}</span>
</Header>

<div class="flex h-full flex-1">
  <!-- Sidebar -->
  <nav class="w-52 shrink-0 overflow-y-auto border-r border-edge p-3 font-mono text-sm">
    <!-- Overview -->
    <a
      href={`/runs/${encodeURIComponent(name)}`}
      class="block w-full rounded px-2 py-1 text-left
          {!hasIter ? 'bg-hover text-fg' : 'text-muted hover:text-fg'}"
    >
      overview
    </a>

    <!-- Iterations -->
    <div class="mt-4 mb-2 px-2 text-faint">iterations</div>
    {#if run}
      {#each run.iterations as _, idx}
        {@const isExpanded = expandedIters.has(idx)}
        {@const isActive = hasIter && currentIter === idx}

        <div>
          <button
            type="button"
            onclick={() => toggleIter(idx)}
            class="flex w-full items-center gap-1 rounded px-2 py-1 text-left
                {isActive ? 'text-fg' : 'text-muted hover:text-fg'}"
          >
            <ChevronRightIcon class="h-3 w-3 {isExpanded ? 'rotate-90' : ''}" />
            <span>{idx}</span>
          </button>

          {#if isExpanded}
            <div class="ml-4 border-l border-edge pl-2">
              {#each ["metrics", "changes", "graph"] as view}
                {@const viewPath = view === "metrics" ? "" : `/${view}`}
                <a
                  href={`/runs/${encodeURIComponent(name)}/${idx}${viewPath}`}
                  class="block w-full rounded px-2 py-0.5 text-left
                      {isIterViewActive(idx, view)
                    ? 'bg-hover text-fg'
                    : 'text-muted hover:text-fg'}"
                >
                  {view}
                </a>
              {/each}
            </div>
          {/if}
        </div>
      {/each}
    {/if}
  </nav>

  <!-- Content -->
  <main class="flex-1 overflow-auto p-6">
    <div class="mx-auto w-full max-w-6xl">
      {@render children()}
    </div>
  </main>
</div>
