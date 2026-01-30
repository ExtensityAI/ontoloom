<script lang="ts">
  import { page } from "$app/state"
  import type { RunDetail } from "$lib/api/types"
  import IterationStepper from "$lib/components/runs/IterationStepper.svelte"
  import { ChartLineIcon, FileDiffIcon, LayoutDashboardIcon, NetworkIcon } from "@lucide/svelte"
  import HeaderRow from "../layout/HeaderRow.svelte"
  import NavItem from "../layout/NavItem.svelte"

  const { run }: { run: RunDetail } = $props()
  const maxIter = $derived(run.iterations.length - 1)
  const paramIter = $derived(Number(page.params.iter))
  const iter = $derived(paramIter || maxIter)

  const path = $derived(`/runs/${encodeURIComponent(run.metadata.name)}`)
  // TODO: when moving through iters, stay on page!
  const iterHref = (idx: number) => `${path}/${idx}`
</script>

<HeaderRow class="top-8 z-10 h-10 text-sm ">
  <NavItem {path}>
    <LayoutDashboardIcon size={12} />
    Overview
  </NavItem>

  <div class="h-full w-px bg-edge"></div>

  <div class={["flex items-center gap-2 transition", !paramIter && "opacity-50 hover:opacity-100"]}>
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
