<script lang="ts">
  import type { PageData } from "./$types"

  let { data }: { data: PageData } = $props()

  const iteration = $derived(data.iteration)
  const prev = $derived(data.previousIteration?.metrics)
  const m = $derived(iteration?.metrics)

  const delta = (curr: number | undefined, prev: number | undefined) => {
    if (curr === undefined || prev === undefined) return null
    const d = curr - prev
    if (d === 0) return null
    return d > 0 ? `+${d}` : `${d}`
  }

  const deltaClass = (curr: number | undefined, prev: number | undefined, invert = false) => {
    if (curr === undefined || prev === undefined) return ""
    const d = curr - prev
    if (d === 0) return "text-faint"
    const isPositive = invert ? d < 0 : d > 0
    return isPositive ? "text-ok" : "text-err"
  }
</script>

<div class="space-y-8">
  <h1 class="text-lg font-semibold text-fg">Iteration {data.iterNum} Metrics</h1>

  {#if m}
    <!-- Primary metrics -->
    <section>
      <h2 class="mb-4 text-sm font-medium text-muted">Overview</h2>
      <div class="grid grid-cols-2 gap-4 sm:grid-cols-3">
        <div class="rounded-lg border border-edge p-4">
          <div class="text-2xl font-semibold text-fg">{m.class_count}</div>
          <div class="mt-1 flex items-center gap-2 text-sm">
            <span class="text-muted">classes</span>
            {#if delta(m.class_count, prev?.class_count)}
              <span class={deltaClass(m.class_count, prev?.class_count)}>{delta(m.class_count, prev?.class_count)}</span>
            {/if}
          </div>
        </div>

        <div class="rounded-lg border border-edge p-4">
          <div class="text-2xl font-semibold text-fg">{m.max_depth}</div>
          <div class="mt-1 flex items-center gap-2 text-sm">
            <span class="text-muted">max depth</span>
            {#if delta(m.max_depth, prev?.max_depth)}
              <span class={deltaClass(m.max_depth, prev?.max_depth)}>{delta(m.max_depth, prev?.max_depth)}</span>
            {/if}
          </div>
        </div>

        <div class="rounded-lg border border-edge p-4">
          <div class="text-2xl font-semibold text-fg">{Math.round(m.property_coverage * 100)}%</div>
          <div class="mt-1 text-sm text-muted">coverage</div>
        </div>
      </div>
    </section>

    <!-- Properties -->
    <section>
      <h2 class="mb-4 text-sm font-medium text-muted">Properties</h2>
      <div class="grid grid-cols-2 gap-4">
        <div class="rounded-lg border border-edge p-4">
          <div class="text-2xl font-semibold text-fg">{m.data_property_count}</div>
          <div class="mt-1 flex items-center gap-2 text-sm">
            <span class="text-muted">data properties</span>
            {#if delta(m.data_property_count, prev?.data_property_count)}
              <span class={deltaClass(m.data_property_count, prev?.data_property_count)}>{delta(m.data_property_count, prev?.data_property_count)}</span>
            {/if}
          </div>
        </div>

        <div class="rounded-lg border border-edge p-4">
          <div class="text-2xl font-semibold text-fg">{m.object_property_count}</div>
          <div class="mt-1 flex items-center gap-2 text-sm">
            <span class="text-muted">object properties</span>
            {#if delta(m.object_property_count, prev?.object_property_count)}
              <span class={deltaClass(m.object_property_count, prev?.object_property_count)}>{delta(m.object_property_count, prev?.object_property_count)}</span>
            {/if}
          </div>
        </div>
      </div>
    </section>

    <!-- Hierarchy -->
    <section>
      <h2 class="mb-4 text-sm font-medium text-muted">Hierarchy</h2>
      <div class="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <div class="rounded-lg border border-edge p-4">
          <div class="text-xl font-semibold text-fg">{m.root_class_count}</div>
          <div class="mt-1 text-sm text-muted">roots</div>
        </div>
        <div class="rounded-lg border border-edge p-4">
          <div class="text-xl font-semibold text-fg">{m.leaf_class_count}</div>
          <div class="mt-1 text-sm text-muted">leaves</div>
        </div>
        <div class="rounded-lg border border-edge p-4">
          <div class="text-xl font-semibold text-fg">{m.orphan_class_count}</div>
          <div class="mt-1 flex items-center gap-2 text-sm">
            <span class="text-muted">orphans</span>
            {#if delta(m.orphan_class_count, prev?.orphan_class_count)}
              <span class={deltaClass(m.orphan_class_count, prev?.orphan_class_count, true)}>{delta(m.orphan_class_count, prev?.orphan_class_count)}</span>
            {/if}
          </div>
        </div>
        <div class="rounded-lg border border-edge p-4">
          <div class="text-xl font-semibold text-fg">{m.avg_branching_factor.toFixed(1)}</div>
          <div class="mt-1 text-sm text-muted">avg branching</div>
        </div>
      </div>
    </section>
  {:else}
    <div class="rounded-lg border border-edge p-8 text-center text-muted">
      No metrics available for this iteration
    </div>
  {/if}
</div>
