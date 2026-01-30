<script lang="ts">
  import type { Snippet } from "svelte"

  const { children }: { children: Snippet } = $props()
</script>

<header class="flex items-center gap-2 border-b border-edge px-4 py-2 font-mono text-sm">
  {@render children()}
</header>
