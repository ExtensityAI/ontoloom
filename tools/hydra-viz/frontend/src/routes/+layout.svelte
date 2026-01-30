<script lang="ts">
  import favicon from "$lib/assets/favicon.svg"
  import Footer from "$lib/components/layout/Footer.svelte"
  import "../layout.css"

  let { children } = $props()
</script>

<svelte:head>
  <link rel="icon" href={favicon} />
  <title>ontology-hydra Visualizer</title>
</svelte:head>

<div class="flex min-h-svh flex-col bg-bg text-fg">
  <div class="flex-1">{@render children()}</div>
  <Footer />
</div>
