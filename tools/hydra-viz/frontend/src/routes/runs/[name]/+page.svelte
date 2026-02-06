<script lang="ts">
  import GrowthCharts from "$lib/components/charts/GrowthCharts.svelte"
  import { formatDateTime } from "$lib/utils/date"
  import type { PageData } from "./$types"

  let { data }: { data: PageData } = $props()

  const iterations = $derived(data.run.iterations)

  const last = $derived.by(() => {
    const withMetrics = iterations.filter(i => i.ontology_metrics)
    return withMetrics.length ? withMetrics[withMetrics.length - 1].ontology_metrics : null
  })
</script>

<div class="mx-auto w-full max-w-6xl space-y-8 px-4 py-8">
  <div>
    <h1 class="text-lg">{data.run.metadata.intent}</h1>
    {#if last}
      <div class="flex items-center gap-2 font-mono text-sm text-muted">
        {iterations.length} iterations
        <div class="h-px w-2 bg-surface"></div>
        {last.counts.n_classes} classes
        <div class="h-px w-2 bg-surface"></div>
        {last.counts.n_data_properties + last.counts.n_object_properties} props
        <div class="h-px w-2 bg-surface"></div>
        depth {last.distributions.class_depth.max}
      </div>
    {/if}
  </div>

  <GrowthCharts {iterations} />

  <dl class="font-mono text-sm text-faint">
    <div class="flex gap-4">
      <dt>created</dt>
      <dd class="text-muted">{formatDateTime(data.run.metadata.created_at)}</dd>
    </div>
    <div class="flex gap-4">
      <dt>iterations</dt>
      <dd class="text-muted">{iterations.length}</dd>
    </div>
  </dl>
</div>
