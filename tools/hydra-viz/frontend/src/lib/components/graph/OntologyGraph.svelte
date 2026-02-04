<script lang="ts">
  import type { Ontology } from "$lib/api/types"
  import forceAtlas2 from "graphology-layout-forceatlas2"
  import FA2LayoutSupervisor from "graphology-layout-forceatlas2/worker"
  import { Sigma } from "sigma"
  import { onDestroy, untrack } from "svelte"
  import { createOntologyGraph } from "./parser"
  import { createEdgeReducer, createNodeReducer } from "./reducers"
  import { createSelection, type NodeSelection } from "./selection"
  import { graphTheme } from "./theme"
  import type { HydraGraph, HydraSigma } from "./types"

  type LayoutSupervisor = InstanceType<typeof FA2LayoutSupervisor>

  const CAMERA_ANIMATION_MS = 300

  let { ontology }: { ontology: Ontology | null } = $props()

  let container: HTMLDivElement | null = $state(null)
  let sigma: HydraSigma | null = $state(null)
  let graph: HydraGraph | null = $state(null)
  let activeSelection: NodeSelection | null = $state(null)
  let layout: LayoutSupervisor | null = $state(null)
  let hoveredNode: string | null = $state(null)

  const getActiveSelection = () => activeSelection
  const getHoveredNode = () => hoveredNode

  const handleNodeClick = (nodeId: string) => {
    if (!graph) return
    activeSelection = createSelection(nodeId, graph)
    sigma?.refresh()
  }

  const clearSelection = () => {
    activeSelection = null
    sigma?.refresh()
  }

  const cleanup = () => {
    layout?.stop()
    layout?.kill()
    sigma?.kill()

    sigma = null
    graph = null
    layout = null
    activeSelection = null
    hoveredNode = null
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
        const newLayout = new FA2LayoutSupervisor(newGraph, {
          settings: layoutSettings,
          backgroundIterations: 1
        })
        newLayout.start()
        layout = newLayout

        // there is a guard for the container below our untrack in the effect!
        const newSigma = new Sigma(newGraph, container as HTMLDivElement, {
          nodeReducer: createNodeReducer(getActiveSelection, getHoveredNode),
          edgeReducer: createEdgeReducer(getActiveSelection),
          allowInvalidContainer: true,
          renderLabels: true,
          labelFont: "system-ui, sans-serif",
          labelSize: 12,
          labelColor: { attribute: "labelColor", color: graphTheme.label },
          defaultEdgeType: "arrow"
        })

        newSigma.on("clickNode", ({ node }) => handleNodeClick(node))
        newSigma.on("clickStage", () => clearSelection())
        newSigma.on("enterNode", ({ node }) => {
          hoveredNode = node
          newSigma.refresh()
        })
        newSigma.on("leaveNode", () => {
          hoveredNode = null
          newSigma.refresh()
        })
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
