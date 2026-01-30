<script lang="ts">
  import RunHeader from "$lib/components/runs/RunHeader.svelte"
  import type { Snippet } from "svelte"
  import type { LayoutData } from "./$types"

  let { data, children }: { data: LayoutData; children: Snippet } = $props()

  const run = $derived(data.run)
</script>

<div class="flex flex-1 flex-col">
  <RunHeader {run} />

  <main class="flex flex-1 flex-col">
    {@render children()}
  </main>
</div>
