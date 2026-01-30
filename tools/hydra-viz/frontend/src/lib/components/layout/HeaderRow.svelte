<script lang="ts">
  import type { Snippet } from "svelte"
  import type { ClassValue } from "svelte/elements"

  const {
    children,
    class: clazz = ""
  }: {
    children: Snippet
    class?: ClassValue
  } = $props()
</script>

<nav
  class={[
    "sticky z-20 flex items-center gap-2 border-b border-b-edge bg-bg/80 px-2 font-mono text-faint backdrop-blur-lg",
    clazz
  ]}
>
  {@render children()}
</nav>
