<script lang="ts">
  import MetricsCharts from "$lib/components/metrics/MetricsCharts.svelte"
  import { formatDateTimeFull } from "$lib/utils/date"
  import { ScrollIcon } from "@lucide/svelte"
  import type { LayoutData } from "./$types"

  let { data }: { data: LayoutData } = $props()

  const finalMetrics = $derived.by(() => {
    if (!data.metrics.points.length) return null
    return data.metrics.points[data.metrics.points.length - 1].metrics
  })
</script>

<div class="mx-auto w-full max-w-6xl space-y-8 px-4 py-8">
  <div>
    <h1 class="text-lg">{data.run.metadata.intent}</h1>
    {#if finalMetrics}
      <div class="flex items-center gap-2 font-mono text-sm text-muted">
        {data.run.iterations.length + 1} iterations
        <div class="h-px w-2 bg-surface"></div>
        {finalMetrics.class_count} classes
        <div class="h-px w-2 bg-surface"></div>
        {finalMetrics.data_property_count + finalMetrics.object_property_count} props
        <div class="h-px w-2 bg-surface"></div>
        depth {finalMetrics.max_depth}
      </div>
    {/if}
  </div>

  <MetricsCharts metrics={data.metrics} currentIteration={-1} />

  <dl class="font-mono text-sm text-faint">
    <div class="flex gap-4">
      <dt>created</dt>
      <dd class="text-muted">{formatDateTimeFull(data.run.metadata.created_at)}</dd>
    </div>
    <div class="flex gap-4">
      <dt>iterations</dt>
      <dd class="text-muted">{data.run.iterations.length}</dd>
    </div>
  </dl>
</div>
