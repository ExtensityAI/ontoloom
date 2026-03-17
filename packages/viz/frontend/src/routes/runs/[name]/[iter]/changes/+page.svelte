<script lang="ts">
  import { badgeClass, displayName, groupOperations } from "$lib/components/runs/operations"
  import MarkdownSection from "$lib/components/ui/MarkdownSection.svelte"
  import type { PageData } from "./$types"

  let { data }: { data: PageData } = $props()

  const iteration = $derived(data.iteration)
  const ops = $derived(iteration?.ops ?? [])
  const groupedOps = $derived(groupOperations(ops))
  const opGroups = $derived.by(() => [
    { label: "Added", color: "text-ok", items: groupedOps.adds },
    { label: "Updated", color: "text-warn", items: groupedOps.updates },
    { label: "Deleted", color: "text-err", items: groupedOps.deletes },
    { label: "Merged", color: "text-info", items: groupedOps.merges }
  ])
</script>

<div class="mx-auto w-full max-w-6xl space-y-8 px-4 py-8">
  <div class="rounded border border-edge bg-surface/40 p-4">
    <h1 class="text-lg">Iteration {iteration?.index ?? "—"} Changes</h1>
    <div class="mt-1 flex flex-wrap items-center gap-3 text-xs text-muted">
      <span>{ops.length} operations</span>
      <span class="text-ok">{groupedOps.adds.length} added</span>
      <span class="text-warn">{groupedOps.updates.length} updated</span>
      <span class="text-err">{groupedOps.deletes.length} deleted</span>
      <span class="text-info">{groupedOps.merges.length} merged</span>
    </div>
  </div>

  <MarkdownSection title="Plan" content={iteration?.plan} color="info" />

  <section class="rounded border border-edge bg-surface/30 p-3">
    <div class="mb-3 flex items-center justify-between">
      <h2 class="text-sm font-medium text-muted">Operations</h2>
      <span class="text-xs text-muted">{ops.length} total</span>
    </div>

    {#if ops.length}
      <div class="grid gap-3 md:grid-cols-2">
        {#each opGroups as group}
          <div class="rounded border border-edge bg-surface/40 p-3">
            <div class="mb-2 flex items-center justify-between text-xs text-muted">
              <span class={group.color}>{group.label}</span>
              <span class="text-faint">{group.items.length}</span>
            </div>
            {#if group.items.length}
              <ul class="space-y-2">
                {#each group.items as op}
                  <li class="flex items-start gap-2">
                    <span class={`shrink-0 border px-2 py-0.5 font-mono text-xs ${badgeClass(op.op)}`}>
                      {op.op}
                    </span>
                    <span class="text-sm text-fg">{displayName(op) || op.op}</span>
                  </li>
                {/each}
              </ul>
            {:else}
              <p class="text-xs text-faint">—</p>
            {/if}
          </div>
        {/each}
      </div>
    {:else}
      <p class="text-sm text-muted">No operations in this iteration</p>
    {/if}
  </section>

  <MarkdownSection title="Review" content={iteration?.review} color="ok" />
</div>
