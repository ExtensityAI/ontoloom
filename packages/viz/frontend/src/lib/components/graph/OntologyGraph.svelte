<script lang="ts">
  import type { Ontology } from "$lib/api/types"
  import forceAtlas2 from "graphology-layout-forceatlas2"
  import FA2LayoutSupervisor from "graphology-layout-forceatlas2/worker"
  import { Sigma } from "sigma"
  import { onDestroy, onMount } from "svelte"
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
  let activeSelection: NodeSelection | null = $state(null)
  let layout: LayoutSupervisor | null = null
  let hoveredNode: string | null = $state(null)
  let lastOntology: Ontology | null = null

  const getActiveSelection = () => activeSelection
  const getHoveredNode = () => hoveredNode

  const handleNodeClick = (nodeId: string) => {
    if (!graph) return
    const attrs = graph.getNodeAttributes(nodeId)
    activeSelection = {
      node: nodeId,
      attrs,
      parents: new Set(attrs.parents),
      children: attrs.children
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

  // TODO: simplify lifecycle
  const buildGraph = () => {
    if (!container) return
    if (!ontology) {
      cleanup()
      lastOntology = null
      return
    }
    if (ontology === lastOntology && graph) return

    cleanup()

    const newGraph = createOntologyGraph(ontology)
    graph = newGraph
    lastOntology = ontology

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
  }

  onMount(() => {
    buildGraph()
    return () => cleanup()
  })

  $effect(() => {
    if (!container) return
    if (ontology !== lastOntology) buildGraph()
  })

  // TODO: simplify
  const panel = $derived.by(() => {
    const nodeId = activeSelection?.node ?? hoveredNode
    if (!nodeId || !graph || !graph.hasNode(nodeId)) return null
    const attrs = graph.getNodeAttributes(nodeId)
    const toLabel = (id: string) => graph.getNodeAttribute(id, "label") as string
    const parents = Array.from(attrs.parents)
      .map((id) => ({ id, label: toLabel(id) }))
      .sort((a, b) => a.label.localeCompare(b.label))
    const children = Array.from(attrs.children)
      .map((id) => ({ id, label: toLabel(id) }))
      .sort((a, b) => a.label.localeCompare(b.label))
    return {
      label: attrs.label,
      parents,
      children,
      isSelected: !!activeSelection
    }
  })
</script>

<div class="absolute inset-0" bind:this={container}></div>

<!-- TODO: simplify this. move to other component possibly! -->
{#if panel}
  <aside
    class="absolute top-16 right-4 z-10 max-h-[calc(100%-6rem)] w-72 overflow-auto rounded border border-edge bg-surface/80 p-3 text-sm backdrop-blur"
  >
    <div class="mb-3 text-xs text-muted uppercase">
      {panel.isSelected ? "selected" : "hovered"}
    </div>
    <div class="mb-4 flex items-center gap-2 text-fg">
      <span
        class="h-2 w-2 rounded-full"
        style={`background-color: ${graphTheme.node.focus.selected}`}
      ></span>
      <span class="truncate" style={`color: ${graphTheme.node.focus.selected}`}>{panel.label}</span>
    </div>

    <div class="space-y-3">
      <div>
        <div class="text-xs text-muted">parents ({panel.parents.length})</div>
        {#if panel.parents.length}
          <ul class="mt-1 space-y-1">
            {#each panel.parents as parent}
              <li class="flex items-center gap-2">
                <span
                  class="h-1.5 w-1.5 rounded-full"
                  style={`background-color: ${graphTheme.node.focus.parent}`}
                ></span>
                <span class="truncate" style={`color: ${graphTheme.node.focus.parent}`}>
                  {parent.label}
                </span>
              </li>
            {/each}
          </ul>
        {:else}
          <div class="mt-1 text-xs text-faint">—</div>
        {/if}
      </div>

      <div>
        <div class="text-xs text-muted">children ({panel.children.length})</div>
        {#if panel.children.length}
          <ul class="mt-1 space-y-1">
            {#each panel.children as child}
              <li class="flex items-center gap-2">
                <span
                  class="h-1.5 w-1.5 rounded-full"
                  style={`background-color: ${graphTheme.node.focus.child}`}
                ></span>
                <span class="truncate" style={`color: ${graphTheme.node.focus.child}`}>
                  {child.label}
                </span>
              </li>
            {/each}
          </ul>
        {:else}
          <div class="mt-1 text-xs text-faint">—</div>
        {/if}
      </div>
    </div>
  </aside>
{/if}

{#if !ontology}
  <div class="absolute inset-0 flex items-center justify-center text-faint">
    No ontology data available
  </div>
{/if}
