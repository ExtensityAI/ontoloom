<script lang="ts">
  import type { Snippet } from "svelte"
  import ExtensityLogo from "./ExtensityLogo.svelte"

  const { children }: { children?: Snippet } = $props()
</script>

<footer></footer>
<header class="flex items-center gap-2 border-t border-edge px-4 py-3 font-mono text-sm">
  {@render children?.()}
  <div class="flex-1"></div>
  <a href="https://extensity.ai">
    <ExtensityLogo class="h-5 -translate-y-px" />
  </a>
</header>
