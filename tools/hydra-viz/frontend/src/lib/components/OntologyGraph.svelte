<script lang="ts">
  import type { Ontology } from "$lib/api/types"
  import { createOntologyGraph } from "$lib/graph/parser"
  import type { HydraGraph, HydraSigma } from "$lib/graph/types"
  import { getCssVar } from "$lib/utils/theme"
  import { createEdgeReducer, createNodeReducer } from "$lib/visualizer/reducers"
  import { createSelection, type NodeSelection } from "$lib/visualizer/selection"
  import { XIcon } from "@lucide/svelte"
  import { Sigma } from "sigma"
  import { onDestroy, untrack } from "svelte"

  const CAMERA_ANIMATION_MS = 300

  let { ontology }: { ontology: Ontology | null } = $props()

  let container: HTMLDivElement
  let sigma: HydraSigma | null = $state(null)
  let graph: HydraGraph | null = $state(null)
  let activeSelection: NodeSelection | null = $state(null)

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

  const cleanup = () => {
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

        const labelColor = getCssVar("--color-fg") || "#f5f5f4"

        const newSigma = new Sigma(newGraph, container, {
          nodeReducer: createNodeReducer(getActiveSelection),
          edgeReducer: createEdgeReducer(getActiveSelection),
          allowInvalidContainer: true,
          renderLabels: true,
          labelFont: "system-ui, sans-serif",
          labelSize: 12,
          labelColor: { color: labelColor },
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

<div bind:this={container} class="h-screen w-screen"></div>

{#if activeSelection}
  <div class="absolute bottom-3 left-3 border border-edge bg-surface p-3">
    <div class="flex items-start gap-4">
      <div>
        <div class="font-semibold text-accent">{activeSelection.node}</div>
        <div class="mt-1 text-sm text-muted">
          Level {activeSelection.attrs.level} ·
          {activeSelection.parents.size} ancestors ·
          {activeSelection.children.size} children
        </div>
      </div>
      <button
        type="button"
        onclick={clearSelection}
        class="shrink-0 p-1 transition-colors hover:bg-hover"
        title="Clear selection"
      >
        <XIcon class="h-4 w-4" />
      </button>
    </div>
  </div>
{/if}

{#if !ontology}
  <div class="absolute inset-0 flex items-center justify-center text-faint">
    No ontology data available
  </div>
{/if}
