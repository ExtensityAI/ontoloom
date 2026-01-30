<script lang="ts">
  import Markdown from "$lib/components/Markdown.svelte"
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

  // TODO: Replace with actual attempts data when available
  const attempts = [{ id: 1, status: "success" as const }]
  let selectedAttempt = $state(1)
  const hasMultipleAttempts = $derived(attempts.length > 1)
</script>

<div class="mx-auto w-full max-w-6xl space-y-12 px-4 py-8">
  <!-- Attempt tabs (placeholder - shown when multiple attempts exist) -->
  {#if hasMultipleAttempts}
    <div class="flex items-center gap-2 font-mono text-sm">
      <span class="text-faint">attempt:</span>
      {#each attempts as attempt}
        <button
          class="px-2 py-1 transition-colors duration-150
            {selectedAttempt === attempt.id
              ? 'bg-fg text-bg'
              : 'text-muted hover:bg-fg hover:text-bg'}"
          onclick={() => (selectedAttempt = attempt.id)}
        >
          {attempt.id}
          {#if attempt.status === "success"}
            <span class="text-ok">✓</span>
          {:else if attempt.status === "rejected"}
            <span class="text-err">✗</span>
          {/if}
        </button>
      {/each}
    </div>
  {/if}

  <!-- Plan -->
  <section class="border-l-2 border-info pl-4">
    <h2 class="mb-3 text-xs font-semibold uppercase tracking-wide text-info">Plan</h2>
    <div class="text-sm">
      {#if iteration?.plan}
        <Markdown content={iteration.plan} />
      {:else}
        <p class="text-muted">No plan for this iteration</p>
      {/if}
    </div>
  </section>

  <!-- Operations -->
  <section class="border-l-2 border-warn pl-4">
    <div class="mb-3 flex items-center gap-4">
      <h2 class="text-xs font-semibold uppercase tracking-wide text-warn">Operations</h2>
      {#if iteration?.ops?.length}
        <div class="flex gap-3 text-xs">
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

    <div class="border border-edge">
      {#if iteration?.ops?.length}
        <ul class="divide-y divide-edge">
          {#each iteration.ops as op}
            <li class="flex items-center gap-3 px-4 py-3">
              <span class="shrink-0 border px-2 py-0.5 font-mono text-sm {opBadgeClass(op.op)}">
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
  <section class="border-l-2 border-ok pl-4">
    <h2 class="mb-3 text-xs font-semibold uppercase tracking-wide text-ok">Review</h2>
    <div class="text-sm">
      {#if iteration?.review}
        <Markdown content={iteration.review} />
      {:else}
        <p class="text-muted">No review for this iteration</p>
      {/if}
    </div>
  </section>
</div>
