<script lang="ts">
  import type { Snippet } from "svelte"
  import ExtensityLogo from "./ExtensityLogo.svelte"

  const { children }: { children?: Snippet } = $props()
</script>

<footer
  class="flex h-12 items-center gap-2 border-t border-t-edge bg-bg/80 px-2 font-mono text-sm text-faint backdrop-blur-lg"
>
  {@render children?.()}
  <div class="flex-1"></div>
  <a href="https://extensity.ai" target="_blank">
    <ExtensityLogo class="h-5 -translate-y-px" />
  </a>
</footer>
