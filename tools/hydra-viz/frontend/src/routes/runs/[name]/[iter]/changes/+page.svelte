<script lang="ts">
  import type { PageData } from "./$types"
  import type { IterationDetail } from "$lib/api/types"

  let { data }: { data: PageData } = $props()

  const iteration = $derived(data.iteration)

  const getOpDisplayName = (op: IterationDetail["ops"][number]): string => {
    if ("name" in op) return op.name
    if ("target_name" in op) return op.target_name
    return ""
  }

  const groupedOps = $derived.by(() => {
    if (!iteration?.ops) return { adds: [], updates: [], deletes: [], merges: [] }
    return {
      adds: iteration.ops.filter((op) => op.op.startsWith("add")),
      updates: iteration.ops.filter((op) => op.op.startsWith("update")),
      deletes: iteration.ops.filter((op) => op.op.startsWith("del")),
      merges: iteration.ops.filter((op) => op.op === "merge_classes")
    }
  })

  const opBadgeClass = (op: string) => {
    if (op.startsWith("add")) return "bg-ok/10 text-ok border-ok/20"
    if (op.startsWith("del")) return "bg-err/10 text-err border-err/20"
    if (op.startsWith("update")) return "bg-warn/10 text-warn border-warn/20"
    if (op === "merge_classes") return "bg-info/10 text-info border-info/20"
    return "bg-surface/70 text-muted border-edge"
  }
</script>

<div class="space-y-8">
  <h1 class="text-lg font-semibold text-fg">Iteration {data.iterNum} Changes</h1>

  <!-- Plan -->
  <section>
    <h2 class="mb-4 text-sm font-medium text-muted">Plan</h2>
    <div class="rounded-lg border border-edge p-4">
      {#if iteration?.plan}
        <pre class="whitespace-pre-wrap font-mono text-sm leading-relaxed text-fg">{iteration.plan}</pre>
      {:else}
        <p class="text-muted">No plan for this iteration</p>
      {/if}
    </div>
  </section>

  <!-- Operations -->
  <section>
    <div class="mb-4 flex items-center gap-4">
      <h2 class="text-sm font-medium text-muted">Operations</h2>
      {#if iteration?.ops?.length}
        <div class="flex gap-3 text-sm">
          {#if groupedOps.adds.length}
            <span class="text-ok">{groupedOps.adds.length} added</span>
          {/if}
          {#if groupedOps.updates.length}
            <span class="text-warn">{groupedOps.updates.length} updated</span>
          {/if}
          {#if groupedOps.deletes.length}
            <span class="text-err">{groupedOps.deletes.length} deleted</span>
          {/if}
          {#if groupedOps.merges.length}
            <span class="text-info">{groupedOps.merges.length} merged</span>
          {/if}
        </div>
      {/if}
    </div>

    <div class="rounded-lg border border-edge">
      {#if iteration?.ops?.length}
        <ul class="divide-y divide-edge">
          {#each iteration.ops as op}
            <li class="flex items-center gap-3 px-4 py-3">
              <span class="shrink-0 rounded border px-2 py-0.5 font-mono text-sm {opBadgeClass(op.op)}">
                {op.op}
              </span>
              <span class="text-sm text-fg">{getOpDisplayName(op)}</span>
            </li>
          {/each}
        </ul>
      {:else}
        <p class="p-4 text-muted">No operations in this iteration</p>
      {/if}
    </div>
  </section>

  <!-- Review -->
  <section>
    <h2 class="mb-4 text-sm font-medium text-muted">Review</h2>
    <div class="rounded-lg border border-edge p-4">
      {#if iteration?.review}
        <pre class="whitespace-pre-wrap font-mono text-sm leading-relaxed text-fg">{iteration.review}</pre>
      {:else}
        <p class="text-muted">No review for this iteration</p>
      {/if}
    </div>
  </section>
</div>
