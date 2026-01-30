<script lang="ts">
  import { page } from "$app/state"
  import type { Snippet } from "svelte"

  const {
    path,
    class: clazz,
    children
  }: { path: string; class?: string; children: Snippet } = $props()

  const active = $derived(page.url.pathname === path)
</script>

<a
  href={path}
  class={[
    "flex h-full items-center gap-1.5 px-2 transition hover:text-fg",
    active && "text-fg",
    clazz
  ]}
>
  {@render children()}
</a>
