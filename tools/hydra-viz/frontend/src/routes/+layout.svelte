<script lang="ts">
  import favicon from "$lib/assets/favicon.svg"
  import Breadcrumbs from "$lib/components/layout/Breadcrumbs.svelte"
  import Footer from "$lib/components/layout/Footer.svelte"
  import HeaderRow from "$lib/components/layout/HeaderRow.svelte"
  import { LineSquiggleIcon } from "@lucide/svelte"
  import "../layout.css"

  const { children } = $props()
</script>

<svelte:head>
  <link rel="icon" href={favicon} />
  <title>ontology-hydra Visualizer</title>
</svelte:head>

<div class="flex min-h-svh flex-col bg-bg text-fg">
  <HeaderRow class="top-0 h-8 border-b-edge text-xs">
    <Breadcrumbs />
    <div class="grow"></div>
    <a
      href="https://github.com/ExtensityAI/ontology-hydra"
      target="_blank"
      class="group flex items-center space-x-1 text-green-500 hover:underline"
    >
      <LineSquiggleIcon class="size-4" /><span>hydra-viz</span>
    </a>
  </HeaderRow>
  <main class="relative flex flex-1 flex-col">
    {@render children()}
  </main>
  <Footer />
</div>
