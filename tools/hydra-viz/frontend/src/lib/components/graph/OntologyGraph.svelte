<script lang="ts">
  import type { Ontology } from "$lib/api/types"
  import forceAtlas2 from "graphology-layout-forceatlas2"
  import ForceAtlas2Layout from "graphology-layout-forceatlas2/worker"
  import { Sigma } from "sigma"
  import { onDestroy, untrack } from "svelte"
  import { createOntologyGraph } from "./parser"
  import { createEdgeReducer, createNodeReducer } from "./reducers"
  import { createSelection, type NodeSelection } from "./selection"
  import { GRAPH_THEME } from "./theme"
  import type { HydraGraph, HydraSigma } from "./types"

  const CAMERA_ANIMATION_MS = 300

  let { ontology }: { ontology: Ontology | null } = $props()

  let container: HTMLDivElement | null = $state(null)
  let sigma: HydraSigma | null = $state(null)
  let graph: HydraGraph | null = $state(null)
  let activeSelection: NodeSelection | null = $state(null)
  let layout: InstanceType<typeof ForceAtlas2Layout> | null = $state(null)

  const getActiveSelection = () => activeSelection

  const handleNodeClick = (nodeId: string) => {
    if (!graph) return
    activeSelection = createSelection(nodeId, graph)
    sigma?.refresh()
  }

  const clearSelection = () => {
    activeSelection = null
    sigma?.refresh()
  }

  const stopLayout = () => {
    layout?.stop()
    layout?.kill()
    layout = null
  }

  const cleanup = () => {
    stopLayout()
    sigma?.kill()
    sigma = null
    graph = null
    activeSelection = null
  }

  onDestroy(() => {
    cleanup()
  })

  $effect(() => {
    const currentOntology = ontology
    if (currentOntology && container) {
      untrack(() => {
        cleanup()

        const newGraph = createOntologyGraph(currentOntology)
        graph = newGraph

        const layoutSettings = forceAtlas2.inferSettings(newGraph)
        const newLayout = new ForceAtlas2Layout(newGraph, {
          settings: layoutSettings,
          backgroundIterations: 1
        })
        newLayout.start()
        layout = newLayout

        if (!container) {
          throw new Error("Container is null")
        }

        const newSigma = new Sigma(newGraph, container, {
          nodeReducer: createNodeReducer(getActiveSelection),
          edgeReducer: createEdgeReducer(getActiveSelection),
          allowInvalidContainer: true,
          renderLabels: true,
          labelFont: "system-ui, sans-serif",
          labelSize: 12,
          labelColor: { color: GRAPH_THEME.label },
          defaultEdgeType: "arrow"
        })

        newSigma.on("clickNode", ({ node }) => handleNodeClick(node))
        newSigma.on("clickStage", () => clearSelection())
        newSigma.getCamera().animatedReset({ duration: CAMERA_ANIMATION_MS })

        sigma = newSigma
      })
    }
  })
</script>

<div class="absolute inset-0" bind:this={container}></div>

{#if !ontology}
  <div class="absolute inset-0 flex items-center justify-center text-faint">
    No ontology data available
  </div>
{/if}
