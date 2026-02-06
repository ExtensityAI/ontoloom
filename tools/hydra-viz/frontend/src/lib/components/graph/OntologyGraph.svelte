<script lang="ts">
  import type { Ontology } from "$lib/api/types"
  import forceAtlas2 from "graphology-layout-forceatlas2"
  import FA2LayoutSupervisor from "graphology-layout-forceatlas2/worker"
  import { Sigma } from "sigma"
  import { onDestroy } from "svelte"
  import { createOntologyGraph } from "./parser"
  import { createEdgeReducer, createNodeReducer } from "./reducers"
  import { graphTheme } from "./theme"
  import type { HydraGraph, HydraSigma, NodeSelection } from "./types"

  type LayoutSupervisor = InstanceType<typeof FA2LayoutSupervisor>

  const CAMERA_ANIMATION_MS = 300

  let { ontology }: { ontology: Ontology | null } = $props()

  let container: HTMLDivElement | null = $state(null)

  // These are imperative refs for Sigma.js -- not used in the template,
  // so plain variables avoid unnecessary reactive tracking.
  let sigma: HydraSigma | null = null
  let graph: HydraGraph | null = null
  let activeSelection: NodeSelection | null = null
  let layout: LayoutSupervisor | null = null
  let hoveredNode: string | null = null

  const getActiveSelection = () => activeSelection
  const getHoveredNode = () => hoveredNode

  const handleNodeClick = (nodeId: string) => {
    if (!graph) return
    const attrs = graph.getNodeAttributes(nodeId)
    activeSelection = {
      node: nodeId,
      attrs,
      parents: new Set(attrs.parents),
      children: attrs.children,
    }
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
    if (!container) return
    if (!ontology) {
      cleanup()
      return
    }

    cleanup()

    const newGraph = createOntologyGraph(ontology)
    graph = newGraph

    const layoutSettings = forceAtlas2.inferSettings(newGraph)
    const newLayout = new FA2LayoutSupervisor(newGraph, {
      settings: layoutSettings,
      backgroundIterations: 1
    })
    newLayout.start()
    layout = newLayout

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
</script>

<div class="absolute inset-0" bind:this={container}></div>

{#if !ontology}
  <div class="absolute inset-0 flex items-center justify-center text-faint">
    No ontology data available
  </div>
{/if}
