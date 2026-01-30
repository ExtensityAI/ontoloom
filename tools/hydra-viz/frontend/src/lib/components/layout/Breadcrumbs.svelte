<script lang="ts" module>
  export type Crumb = { label: string; href?: string }
</script>

<script lang="ts">
  const { crumbs }: { crumbs: Crumb[] } = $props()
</script>

<nav class="flex items-center">
  {#each crumbs as crumb, i}
    {#if i > 0}
      <span class="text-faint">/</span>
    {/if}
    {#if crumb.href}
      <a href={crumb.href} class="px-2 py-1 text-faint transition-colors hover:text-fg">
        {crumb.label}
      </a>
    {:else}
      <span class="px-2 py-1 text-fg">{crumb.label}</span>
    {/if}
  {/each}
</nav>
