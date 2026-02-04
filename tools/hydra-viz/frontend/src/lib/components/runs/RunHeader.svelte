<script lang="ts">
  import { page } from "$app/state"
  import type { RunDetail } from "$lib/api/types"
  import IterationStepper from "$lib/components/runs/IterationStepper.svelte"
  import { getIterationPath, getRunPath } from "$lib/utils/navigation"
  import { ChartLineIcon, FileDiffIcon, LayoutDashboardIcon, NetworkIcon } from "@lucide/svelte"
  import HeaderRow from "../layout/HeaderRow.svelte"
  import NavItem from "../layout/NavItem.svelte"

  const { run }: { run: RunDetail } = $props()

  const nav = $derived.by(() => {
    const maxIter = run.iterations.length - 1
    const paramIter = Number(page.params.iter)
    const iter = Number.isNaN(paramIter) ? maxIter : paramIter
    const view = page.url.pathname.includes("graph")
      ? "graph"
      : page.url.pathname.includes("changes")
        ? "changes"
        : ""
    const path = getRunPath(run.metadata.id)
    const iterHref = (idx: number) => getIterationPath(run.metadata.id, idx) + "/" + view
    return { maxIter, iter, view, path, iterHref }
  })
</script>

<HeaderRow class="top-8 z-10 h-10 text-sm ">
  <NavItem path={nav.path}>
    <LayoutDashboardIcon size={12} />
    Overview
  </NavItem>

  <div class="h-full w-px bg-edge"></div>

  <div class={"flex items-center gap-2 transition"}>
    <IterationStepper current={nav.iter} max={nav.maxIter} getHref={nav.iterHref} />

    <NavItem path={`${nav.path}/${nav.iter}`}>
      <ChartLineIcon size={12} /> Metrics
    </NavItem>
    <NavItem path={`${nav.path}/${nav.iter}/changes`}>
      <FileDiffIcon size={12} /> Changes
    </NavItem>
    <NavItem path={`${nav.path}/${nav.iter}/graph`}>
      <NetworkIcon size={12} /> Graph
    </NavItem>
  </div>
</HeaderRow>
