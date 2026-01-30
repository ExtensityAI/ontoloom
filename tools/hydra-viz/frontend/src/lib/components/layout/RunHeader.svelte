<script lang="ts">
  import { page } from "$app/stores"
  import type { RunDetail } from "$lib/api/types"
  import Breadcrumbs from "$lib/components/layout/Breadcrumbs.svelte"
  import IterationStepper from "$lib/components/layout/IterationStepper.svelte"
  import { ChartLine, FileDiff, LayoutDashboard, Network } from "@lucide/svelte"

  const { run }: { run: RunDetail | null } = $props()

  const name = $derived($page.params.name!)
  const iterParam = $derived($page.params.iter)
  const iterMax = $derived(run ? run.iterations.length - 1 : -1)
  const parsedIter = $derived(iterParam ? parseInt(iterParam, 10) : NaN)
  const hasIter = $derived(iterParam !== undefined)
  const canNavigate = $derived(iterMax >= 0)

  const currentIter = $derived.by(() => {
    if (!Number.isNaN(parsedIter) && parsedIter >= 0 && parsedIter <= iterMax) return parsedIter
    return iterMax >= 0 ? iterMax : 0
  })

  const currentView = $derived.by(() => {
    if (!hasIter) return "overview"
    const last = $page.url.pathname.split("/").filter(Boolean).at(-1)
    return last && isNaN(parseInt(last, 10)) ? last : "metrics"
  })

  const basePath = $derived(`/runs/${encodeURIComponent(name)}`)
  const iterViewPath = $derived(
    currentView === "overview" || currentView === "metrics" ? "" : `/${currentView}`
  )
  const iterHref = (idx: number) => `${basePath}/${idx}${iterViewPath}`
  const viewHref = (view: string) =>
    view === "overview"
      ? basePath
      : `${basePath}/${currentIter}${view === "metrics" ? "" : `/${view}`}`

  const link = "text-faint hover:text-fg transition-colors"
  const activeLink = "text-fg"

  const viewIcons: Record<string, typeof ChartLine> = {
    metrics: ChartLine,
    changes: FileDiff,
    graph: Network
  }

  const breadcrumbs = $derived($page.data.breadcrumbs ?? [])
</script>

<header class="sticky top-0 z-10 border-b border-edge bg-bg/80 font-mono text-sm backdrop-blur-lg">
  <div class="flex items-center justify-between px-2 py-1">
    <Breadcrumbs crumbs={breadcrumbs} />
    {#if canNavigate}
      <span class="px-2 py-1 text-faint">{iterMax + 1} iterations</span>
    {/if}
  </div>

  <nav class="flex border-t border-edge px-2 py-1">
    <a
      href={basePath}
      class="flex items-center gap-1.5 px-2 py-1 {!hasIter ? activeLink : link}"
      aria-current={!hasIter ? "page" : undefined}
    >
      <LayoutDashboard size={14} />
      overview
    </a>

    {#if canNavigate}
      <div
        class="ml-2 flex items-center border-l border-edge pl-2 transition-opacity {!hasIter
          ? 'opacity-40 hover:opacity-100'
          : ''}"
      >
        <IterationStepper current={currentIter} max={iterMax} getHref={iterHref} />

        <span class="mx-1 text-faint/50">:</span>

        {#each ["metrics", "changes", "graph"] as view}
          {@const Icon = viewIcons[view]}
          <a
            href={viewHref(view)}
            class="flex items-center gap-1.5 px-2 py-1 {currentView === view ? activeLink : link}"
            aria-current={currentView === view ? "page" : undefined}
          >
            <Icon size={14} />
            {view}
          </a>
        {/each}
      </div>
    {/if}
  </nav>
</header>
