<script lang="ts">
  import { formatDateTime } from "$lib/utils/date"
  import { coverage } from "$lib/utils/format"
  import LineChart from "$lib/components/charts/LineChart.svelte"
  import type { IterationSummary, OntologyMetrics } from "$lib/api/types"
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
    metricIterations.length
      ? metricIterations[metricIterations.length - 1].ontology_metrics
      : null
  )

  const signed = (value: number, digits = 0) => {
    const rounded = digits ? Number(value.toFixed(digits)) : Math.round(value)
    const sign = rounded > 0 ? "+" : ""
    const text = digits ? rounded.toFixed(digits) : String(rounded)
    return `${sign}${text}`
  }

  const coveragePct = (m: OntologyMetrics) => Math.round(coverage(m) * 100)

  const notable = $derived.by(() => {
    if (metricIterations.length < 2) return []
    let classJump = { index: metricIterations[1].index, delta: 0 }
    let depthIncrease = { index: metricIterations[1].index, delta: 0 }
    let coverageDrop = { index: metricIterations[1].index, delta: 0 }
    for (let i = 1; i < metricIterations.length; i += 1) {
      const prev = metricIterations[i - 1].ontology_metrics
      const curr = metricIterations[i].ontology_metrics
      const dClasses = curr.counts.n_classes - prev.counts.n_classes
      if (Math.abs(dClasses) > Math.abs(classJump.delta)) {
        classJump = { index: metricIterations[i].index, delta: dClasses }
      }
      const dDepth = curr.distributions.class_depth.max - prev.distributions.class_depth.max
      if (dDepth > depthIncrease.delta) {
        depthIncrease = { index: metricIterations[i].index, delta: dDepth }
      }
      const dCoverage = coverage(curr) - coverage(prev)
      if (dCoverage < coverageDrop.delta) {
        coverageDrop = { index: metricIterations[i].index, delta: dCoverage }
      }
    }
    return [
      {
        label: "Biggest class jump",
        index: classJump.index,
        delta: classJump.delta,
        unit: "",
        digits: 0
      },
      {
        label: "Biggest depth increase",
        index: depthIncrease.index,
        delta: depthIncrease.delta,
        unit: "",
        digits: 0
      },
      {
        label: "Biggest coverage drop",
        index: coverageDrop.index,
        delta: coverageDrop.delta * 100,
        unit: "pp",
        digits: 1
      }
    ]
  })

  const timeline = $derived.by(() =>
    iterations.map((iter, idx) => {
      const prev = idx > 0 ? iterations[idx - 1]?.ontology_metrics : null
      const metrics = iter.ontology_metrics
      if (!metrics) {
        return { index: iter.index, hasMetrics: false }
      }
      return {
        index: iter.index,
        hasMetrics: true,
        classes: metrics.counts.n_classes,
        props: metrics.counts.n_properties,
        coverage: coverage(metrics),
        depth: metrics.distributions.class_depth.max,
        deltaClasses: prev ? metrics.counts.n_classes - prev.counts.n_classes : null,
        deltaProps: prev ? metrics.counts.n_properties - prev.counts.n_properties : null,
        deltaCoverage: prev ? coverage(metrics) - coverage(prev) : null,
        deltaDepth: prev ? metrics.distributions.class_depth.max - prev.distributions.class_depth.max : null
      }
    })
  )

  const labels = $derived(metricIterations.map(iter => iter.index))

  const growthSeries = $derived.by(() => [
    {
      name: "Classes",
      color: "accent" as const,
      data: metricIterations.map(iter => iter.ontology_metrics.counts.n_classes)
    },
    {
      name: "Properties",
      color: "warn" as const,
      data: metricIterations.map(iter => iter.ontology_metrics.counts.n_properties)
    }
  ])

  const qualitySeries = $derived.by(() => [
    {
      name: "Coverage",
      color: "ok" as const,
      data: metricIterations.map(iter =>
        Number((coverage(iter.ontology_metrics) * 100).toFixed(1))
      )
    },
    {
      name: "Max Depth",
      color: "warn" as const,
      data: metricIterations.map(iter => iter.ontology_metrics.distributions.class_depth.max),
      yAxisIndex: 1
    }
  ])
</script>

<div class="mx-auto w-full max-w-6xl space-y-8 px-4 py-8">
  <div class="rounded border border-edge bg-surface/40 p-4">
    <h1 class="text-lg">{data.run.metadata.intent}</h1>
    <div class="flex items-center gap-2 font-mono text-sm text-muted">
      {data.run.metadata.id}
      <div class="h-px w-2 bg-surface"></div>
      {iterations.length} iterations
      {#if last}
        <div class="h-px w-2 bg-surface"></div>
        {last.counts.n_classes} classes
        <div class="h-px w-2 bg-surface"></div>
        {last.counts.n_properties} props
        <div class="h-px w-2 bg-surface"></div>
        depth {last.distributions.class_depth.max}
      {/if}
    </div>
  </div>

  {#if last && first}
    <section>
      <h2 class="mb-4 text-sm font-medium text-muted">Summary</h2>
      <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div class="relative overflow-hidden rounded border border-edge bg-surface/40 p-3">
          <div class="absolute inset-x-0 top-0 h-0.5 bg-accent"></div>
          <div class="text-xs text-muted">classes</div>
          <div class="font-mono text-lg">{last.counts.n_classes}</div>
          <div class="text-xs text-faint">
            Δ {signed(last.counts.n_classes - first.counts.n_classes)}
          </div>
        </div>
        <div class="relative overflow-hidden rounded border border-edge bg-surface/40 p-3">
          <div class="absolute inset-x-0 top-0 h-0.5 bg-info"></div>
          <div class="text-xs text-muted">properties</div>
          <div class="font-mono text-lg">{last.counts.n_properties}</div>
          <div class="text-xs text-faint">
            Δ {signed(last.counts.n_properties - first.counts.n_properties)}
          </div>
        </div>
        <div class="relative overflow-hidden rounded border border-edge bg-surface/40 p-3">
          <div class="absolute inset-x-0 top-0 h-0.5 bg-warn"></div>
          <div class="text-xs text-muted">max depth</div>
          <div class="font-mono text-lg">{last.distributions.class_depth.max}</div>
          <div class="text-xs text-faint">
            Δ {signed(last.distributions.class_depth.max - first.distributions.class_depth.max)}
          </div>
        </div>
        <div class="relative overflow-hidden rounded border border-edge bg-surface/40 p-3">
          <div class="absolute inset-x-0 top-0 h-0.5 bg-ok"></div>
          <div class="text-xs text-muted">coverage</div>
          <div class="font-mono text-lg">{coveragePct(last)}%</div>
          <div class="text-xs text-faint">
            Δ {signed((coverage(last) - coverage(first)) * 100, 1)}pp
          </div>
        </div>
      </div>
    </section>
  {:else}
    <div class="border border-edge p-6 text-sm text-muted">No metrics data available</div>
  {/if}

  {#if notable.length}
    <section>
      <h2 class="mb-4 text-sm font-medium text-muted">Notable Changes</h2>
      <ul class="divide-y divide-edge border border-edge bg-surface/30 text-sm">
        {#each notable as item}
          <li class="flex items-center justify-between gap-4 px-3 py-2 odd:bg-surface/30">
            <span class="text-muted">{item.label}</span>
            <span class="font-mono text-fg">
              iter {item.index} · {signed(item.delta, item.digits)}{item.unit}
            </span>
          </li>
        {/each}
      </ul>
    </section>
  {/if}

  {#if metricIterations.length}
    <section>
      <h2 class="mb-4 text-sm font-medium text-muted">Trends</h2>
      <div class="grid gap-4 lg:grid-cols-2">
        <div class="rounded border border-edge bg-surface/30 p-3">
          <LineChart title="Growth" {labels} series={growthSeries} height={180} />
        </div>
        <div class="rounded border border-edge bg-surface/30 p-3">
          <LineChart
            title="Coverage vs Depth"
            {labels}
            series={qualitySeries}
            percent={true}
            secondaryAxis={true}
            height={180}
          />
        </div>
      </div>
    </section>
  {/if}

  <section>
    <h2 class="mb-4 text-sm font-medium text-muted">Iteration Timeline</h2>
    <ul class="divide-y divide-edge border border-edge bg-surface/30 text-sm">
      {#each timeline as row}
        <li class="flex items-center justify-between gap-4 px-3 py-2 odd:bg-surface/30">
          <a
            href={`/runs/${data.run.metadata.id}/${row.index}`}
            class="font-mono text-fg hover:underline"
          >
            iter {row.index}
          </a>
          {#if row.hasMetrics}
            <div class="flex flex-wrap items-center gap-3 text-xs text-muted">
              <span>
                classes {row.classes}
                <span class="text-faint">
                  ({row.deltaClasses === null ? "—" : signed(row.deltaClasses)})
                </span>
              </span>
              <span>
                props {row.props}
                <span class="text-faint">
                  ({row.deltaProps === null ? "—" : signed(row.deltaProps)})
                </span>
              </span>
              <span>
                depth {row.depth}
                <span class="text-faint">
                  ({row.deltaDepth === null ? "—" : signed(row.deltaDepth)})
                </span>
              </span>
              <span>
                coverage {Math.round(row.coverage * 100)}%
                <span class="text-faint">
                  ({row.deltaCoverage === null ? "—" : signed(row.deltaCoverage * 100, 1)}pp)
                </span>
              </span>
            </div>
          {:else}
            <span class="text-xs text-muted">no metrics</span>
          {/if}
        </li>
      {/each}
    </ul>
  </section>

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
        {data.run.metadata.input_files.length
          ? data.run.metadata.input_files.join(", ")
          : "—"}
      </dd>
    </div>
  </dl>
</div>
