<script lang="ts">
  import MetricsCharts from "$lib/components/MetricsCharts.svelte"
  import { formatDateTimeFull } from "$lib/utils/date"
  import type { LayoutData } from "./$types"

  let { data }: { data: LayoutData } = $props()

  const run = $derived(data.run)
  const metrics = $derived(data.metrics)

  const finalMetrics = $derived.by(() => {
    if (!metrics?.points.length) return null
    return metrics.points[metrics.points.length - 1].metrics
  })
</script>

<div class="space-y-6">
  {#if run?.metadata.intent}
    <p class="text-muted">{run.metadata.intent}</p>
  {/if}

  {#if finalMetrics}
    <div class="font-mono text-sm text-muted">
      {finalMetrics.class_count} classes ·
      {finalMetrics.data_property_count + finalMetrics.object_property_count} props ·
      depth {finalMetrics.max_depth} ·
      {Math.round(finalMetrics.property_coverage * 100)}% coverage
    </div>
  {/if}

  {#if metrics}
    <MetricsCharts {metrics} currentIteration={-1} />
  {/if}

  {#if run}
    <dl class="font-mono text-sm text-faint">
      <div class="flex gap-4">
        <dt>created</dt>
        <dd class="text-muted">{formatDateTimeFull(run.metadata.created_at)}</dd>
      </div>
      <div class="flex gap-4">
        <dt>iterations</dt>
        <dd class="text-muted">{run.iterations.length}</dd>
      </div>
    </dl>
  {/if}
</div>
