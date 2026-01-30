<script lang="ts">
  import { page } from "$app/state"
  import favicon from "$lib/assets/favicon.svg"
  import Breadcrumbs from "$lib/components/layout/Breadcrumbs.svelte"
  import Footer from "$lib/components/layout/Footer.svelte"
  import HeaderRow from "$lib/components/layout/HeaderRow.svelte"
  import "../layout.css"

  const { children } = $props()

  const breadcrumbs = $derived(page.data.breadcrumbs ?? [])
</script>

<svelte:head>
  <link rel="icon" href={favicon} />
  <title>ontology-hydra Visualizer</title>
</svelte:head>

<div class="flex min-h-svh flex-col bg-bg text-fg">
  <HeaderRow class="top-0 h-8 border-b-edge text-xs">
    <Breadcrumbs crumbs={breadcrumbs} />
  </HeaderRow>
  {@render children()}
  <Footer />
</div>
