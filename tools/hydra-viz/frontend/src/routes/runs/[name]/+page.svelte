<script lang="ts">
  import type { IterationSummary, OntologyMetrics } from "$lib/api/types"
  import LineChart from "$lib/components/charts/LineChart.svelte"
  import { formatDateTime } from "$lib/utils/date"
  import { coverage } from "$lib/utils/format"
  import type { PageData } from "./$types"

  let { data }: { data: PageData } = $props()

  const iterations = $derived(data.run.iterations)

  const metricIterations = $derived(
    iterations.filter(
      (
        i
      ): i is IterationSummary & {
        ontology_metrics: NonNullable<IterationSummary["ontology_metrics"]>
      } => i.ontology_metrics !== null
    )
  )

  const first = $derived.by(() =>
    metricIterations.length ? metricIterations[0].ontology_metrics : null
  )
  const last = $derived.by(() =>
    metricIterations.length ? metricIterations[metricIterations.length - 1].ontology_metrics : null
  )

  const signed = (value: number, digits = 0) => {
    const rounded = digits ? Number(value.toFixed(digits)) : Math.round(value)
    const sign = rounded > 0 ? "+" : ""
    const text = digits ? rounded.toFixed(digits) : String(rounded)
    return `${sign}${text}`
  }

  const coveragePct = (m: OntologyMetrics) => Math.round(coverage(m) * 100)

  const labels = $derived(metricIterations.map((iter) => iter.index))

  const growthSeries = $derived.by(() => [
    {
      name: "Classes",
      color: "metricClasses" as const,
      data: metricIterations.map((iter) => iter.ontology_metrics.counts.n_classes)
    },
    {
      name: "Properties",
      color: "metricProperties" as const,
      data: metricIterations.map((iter) => iter.ontology_metrics.counts.n_properties)
    }
  ])

  const qualitySeries = $derived.by(() => [
    {
      name: "Coverage",
      color: "metricCoverage" as const,
      data: metricIterations.map((iter) =>
        Number((coverage(iter.ontology_metrics) * 100).toFixed(1))
      )
    },
    {
      name: "Max Depth",
      color: "metricDepth" as const,
      data: metricIterations.map((iter) => iter.ontology_metrics.distributions.class_depth.max),
      yAxisIndex: 1
    }
  ])
</script>

<div class="mx-auto w-full max-w-6xl space-y-8 px-4 py-8">
  <div>
    <h1 class="text-xl">{data.run.metadata.title}</h1>
    <div class="flex items-center gap-2 text-sm text-muted">
      {data.run.metadata.id}
      <div class="h-px w-1 bg-muted"></div>
      {iterations.length} iterations
    </div>
  </div>

  {#if last && first}
    <section>
      <h2 class="mb-4 text-sm font-medium text-muted">Summary</h2>
      <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div class="relative overflow-hidden rounded border border-edge bg-surface/40 p-3">
          <div class="absolute inset-x-0 top-0 h-0.5 bg-metric-classes"></div>
          <div class="text-xs text-muted">classes</div>
          <div class="font-mono text-lg">{last.counts.n_classes}</div>
        </div>
        <div class="relative overflow-hidden rounded border border-edge bg-surface/40 p-3">
          <div class="absolute inset-x-0 top-0 h-0.5 bg-metric-properties"></div>
          <div class="text-xs text-muted">properties</div>
          <div class="font-mono text-lg">{last.counts.n_properties}</div>
        </div>
        <div class="relative overflow-hidden rounded border border-edge bg-surface/40 p-3">
          <div class="absolute inset-x-0 top-0 h-0.5 bg-metric-depth"></div>
          <div class="text-xs text-muted">max depth</div>
          <div class="font-mono text-lg">{last.distributions.class_depth.max}</div>
        </div>
        <div class="relative overflow-hidden rounded border border-edge bg-surface/40 p-3">
          <div class="absolute inset-x-0 top-0 h-0.5 bg-metric-coverage"></div>
          <div class="text-xs text-muted">coverage</div>
          <div class="font-mono text-lg">{coveragePct(last)}%</div>
        </div>
      </div>
    </section>
  {:else}
    <div class="border border-edge p-6 text-sm text-muted">No metrics data available</div>
  {/if}

  {#if metricIterations.length}
    <section>
      <h2 class="mb-4 text-sm font-medium text-muted">Trends</h2>
      <div class="grid gap-4 lg:grid-cols-2">
        <LineChart title="Growth" {labels} series={growthSeries} height={180} />
        <LineChart
          title="Coverage vs Depth"
          {labels}
          series={qualitySeries}
          percent={true}
          secondaryAxis={true}
          height={180}
        />
      </div>
    </section>
  {/if}

  {#if last}
    <section>
      <h2 class="mb-4 text-sm font-medium text-muted">Quality Signals</h2>
      <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div class="rounded border border-edge bg-surface/30 p-3">
          <div class="text-xs text-muted">root classes</div>
          <div class="font-mono text-lg">{last.counts.n_root_classes}</div>
        </div>
        <div class="rounded border border-edge bg-surface/30 p-3">
          <div class="text-xs text-muted">leaf classes</div>
          <div class="font-mono text-lg">{last.counts.n_leaf_classes}</div>
        </div>
        <div class="rounded border border-edge bg-surface/30 p-3">
          <div class="text-xs text-muted">root / leaf</div>
          <div class="font-mono text-lg">
            {last.counts.n_leaf_classes
              ? (last.counts.n_root_classes / last.counts.n_leaf_classes).toFixed(2)
              : "—"}
          </div>
        </div>
        <div class="rounded border border-edge bg-surface/30 p-3">
          <div class="text-xs text-muted">classes w/ no props</div>
          <div class="font-mono text-lg">{last.counts.classes_with_no_properties}</div>
        </div>
        <div class="rounded border border-edge bg-surface/30 p-3">
          <div class="text-xs text-muted">avg branching</div>
          <div class="font-mono text-lg">
            {last.distributions.subclasses_per_class.mean.toFixed(2)}
          </div>
        </div>
        <div class="rounded border border-edge bg-surface/30 p-3">
          <div class="text-xs text-muted">avg superclasses</div>
          <div class="font-mono text-lg">
            {last.distributions.superclasses_per_class.mean.toFixed(2)}
          </div>
        </div>
        <div class="rounded border border-edge bg-surface/30 p-3">
          <div class="text-xs text-muted">avg data props</div>
          <div class="font-mono text-lg">
            {last.distributions.data_props_per_class.mean.toFixed(2)}
          </div>
        </div>
        <div class="rounded border border-edge bg-surface/30 p-3">
          <div class="text-xs text-muted">avg object props</div>
          <div class="font-mono text-lg">
            {last.distributions.object_props_out_per_class.mean.toFixed(2)}
          </div>
        </div>
      </div>
    </section>
  {/if}

  <dl class="grid gap-2 rounded border border-edge bg-surface/30 p-3 font-mono text-sm text-faint">
    <div class="flex gap-4">
      <dt>created</dt>
      <dd class="text-muted">{formatDateTime(data.run.metadata.created_at)}</dd>
    </div>
    <div class="flex gap-4">
      <dt>iterations</dt>
      <dd class="text-muted">{iterations.length}</dd>
    </div>
    <div class="flex gap-4">
      <dt>input files</dt>
      <dd class="text-muted">
        {data.run.metadata.input_files.length ? data.run.metadata.input_files.join(", ") : "—"}
      </dd>
    </div>
    <div class="flex gap-4">
      <dt>intent</dt>
      <dd class="text-muted">
        {data.run.metadata.intent || "—"}
      </dd>
    </div>
  </dl>
</div>
