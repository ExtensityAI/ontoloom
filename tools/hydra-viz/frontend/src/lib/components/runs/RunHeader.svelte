<script lang="ts">
  import { page } from "$app/state"
  import type { RunDetail } from "$lib/api/types"
  import IterationStepper from "$lib/components/runs/IterationStepper.svelte"
  import { getIterationPath, getRunPath } from "$lib/utils/navigation"
  import { ChartLineIcon, FileDiffIcon, LayoutDashboardIcon, NetworkIcon } from "@lucide/svelte"
  import HeaderRow from "../layout/HeaderRow.svelte"
  import NavItem from "../layout/NavItem.svelte"

  const { run }: { run: RunDetail } = $props()
  const maxIter = $derived(run.iterations.length - 1)
  const paramIter = $derived(Number(page.params.iter))
  const iter = $derived(Number.isNaN(paramIter) ? maxIter : paramIter)

  const view = $derived(
    page.url.pathname.includes("graph")
      ? "graph"
      : page.url.pathname.includes("changes")
        ? "changes"
        : ""
  )

  const path = $derived(getRunPath(run.metadata.id))
  const iterHref = (idx: number) => getIterationPath(run.metadata.id, idx) + "/" + view
</script>

<HeaderRow class="top-8 z-10 h-10 text-sm ">
  <NavItem {path}>
    <LayoutDashboardIcon size={12} />
    Overview
  </NavItem>

  <div class="h-full w-px bg-edge"></div>

  <div class={"flex items-center gap-2 transition"}>
    <IterationStepper current={iter} max={maxIter} getHref={iterHref} />

    <NavItem path={`${path}/${iter}`}>
      <ChartLineIcon size={12} /> Metrics
    </NavItem>
    <NavItem path={`${path}/${iter}/changes`}>
      <FileDiffIcon size={12} /> Changes
    </NavItem>
    <NavItem path={`${path}/${iter}/graph`}>
      <NetworkIcon size={12} /> Graph
    </NavItem>
  </div>
</HeaderRow>
