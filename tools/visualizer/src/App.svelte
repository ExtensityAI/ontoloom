<script lang="ts">
    import { onDestroy } from "svelte"
    import Sigma from "sigma"
    import Graph from "graphology"
    import forceAtlas2, { inferSettings } from "graphology-layout-forceatlas2"
    import { ontologyExportSchema } from "../lib/schema"
    import { createOntologyGraph } from "../lib/graph"
    import { FileInput } from "lucide-svelte/icons"
    import { tooltip } from "../lib/utils/tooltip"

    const levelColors = [
        "#ec003f", // rose-500 (root)
        "#fd9a00", // amber-500
        "#7ccf00", // lime-500
        "#22c55e", // green-500
        "#14b8a6", // teal-500
        "#3b82f6", // blue-500
        "#8b5cf6", // violet-500
        "#ec4899", // pink-500
        "#64748b", // slate-500
    ]

    interface State {
        selectedNode: string | null
        relatedNodes: Set<string>
        connectedEdges: Set<string>
    }

    let isLoading = $state(false)
    let error = $state("")
    let fileName = $state("")

    let container: HTMLDivElement | undefined = $state()
    let sigma: Sigma | null = $state(null)
    let graph: Graph | null = $state(null)
    let viewerState: State = $state({
        selectedNode: null,
        relatedNodes: new Set(),
        connectedEdges: new Set(),
    })

    const getRelatedNodes = (g: Graph, node: string): Set<string> => {
        const related = new Set<string>([node])
        // Get all neighbors (both inbound and outbound)
        g.forEachNeighbor(node, (neighbor) => related.add(neighbor))
        return related
    }

    const getConnectedEdges = (g: Graph, node: string): Set<string> => {
        const edges = new Set<string>()
        g.forEachEdge(node, (edge) => edges.add(edge))
        return edges
    }

    const updateState = (newState: Partial<State>) => {
        viewerState = { ...viewerState, ...newState }
        sigma?.refresh()
    }

    onDestroy(() => sigma?.kill())

    function ensurePositions(graph: Graph) {
        let i = 0
        graph.forEachNode((node, attrs) => {
            const x = parseFloat(String(attrs.x ?? ""))
            const y = parseFloat(String(attrs.y ?? ""))
            const angle = (i++ / graph.order) * Math.PI * 2
            graph.setNodeAttribute(
                node,
                "x",
                Number.isFinite(x) ? x : Math.cos(angle) * 100,
            )
            graph.setNodeAttribute(
                node,
                "y",
                Number.isFinite(y) ? y : Math.sin(angle) * 100,
            )
        })
    }
    const load = async (file: File) => {
        if (isLoading) isLoading = true
        error = ""

        try {
            const content = await file.text()
            const G = createOntologyGraph(
                ontologyExportSchema.parse(JSON.parse(content)),
            )

            // store graph reference for hover logic
            graph = G

            // compute initial positions
            ensurePositions(G)

            // run ForceAtlas2 to layout the graph
            forceAtlas2.assign(G, {
                iterations: 50000,
                settings: { ...inferSettings(G) },
            })

            // destroy previous instance
            sigma?.kill()

            sigma = new Sigma(G, container!, {
                renderLabels: true,
                renderEdgeLabels: true,
                nodeReducer: (node, data) => {
                    const isSelected = viewerState.selectedNode === node
                    const isRelated = viewerState.relatedNodes.has(node)
                    const hasSelection = viewerState.selectedNode !== null

                    let color = levelColors[data.level]
                    if (hasSelection && !isSelected && !isRelated) {
                        color = "#e5e5e5" // gray out unrelated nodes
                    }

                    return {
                        ...data,
                        color,
                        size: 8 + data.inverseLevel * 4,
                        zIndex: isSelected ? 2 : isRelated ? 1 : 0,
                    }
                },
                edgeReducer: (edge, data) => {
                    const isConnected = viewerState.connectedEdges.has(edge)
                    const hasSelection = viewerState.selectedNode !== null

                    let color: string
                    if (data.tag === "hierarchy") {
                        color = hasSelection
                            ? isConnected
                                ? "#a3a3a3" // darker gray for connected hierarchy
                                : "#f5f5f5" // lighter gray for unconnected hierarchy
                            : "#e5e5e5" // default gray
                    } else {
                        color = hasSelection
                            ? isConnected
                                ? "#dc2626" // darker red for connected props
                                : "#fecaca" // lighter red for unconnected props
                            : "#f87171" // default red
                    }

                    return {
                        ...data,
                        color,
                        size: isConnected ? 3 : data.size,
                        zIndex: isConnected ? 1 : 0,
                        label:
                            data.source === viewerState.selectedNode ||
                            data.target === viewerState.selectedNode
                                ? data.label
                                : "",
                    }
                },
            })

            sigma.on("enterNode", ({ node }) => {
                if (graph) {
                    updateState({
                        selectedNode: node,
                        relatedNodes: getRelatedNodes(graph, node),
                        connectedEdges: getConnectedEdges(graph, node),
                    })
                }
            })

            sigma.on("leaveNode", () => {
                updateState({
                    selectedNode: null,
                    relatedNodes: new Set(),
                    connectedEdges: new Set(),
                })
            })

            fileName = file.name
            isLoading = false
        } catch (e) {
            console.error(e)
            error =
                e instanceof Error
                    ? e.message
                    : typeof e === "string"
                      ? e
                      : "Failed to load file"
        } finally {
            isLoading = false
        }
    }

    const onInput = (e: Event) => {
        const input = e.target as HTMLInputElement
        if (input.files?.[0]) load(input.files[0])
        input.value = ""
    }
</script>

<main class="relative min-h-screen">
    <footer class="absolute bottom-0 left-0 right-0 z-100 p-2 flex group">
        <label class="cursor-pointer p-1" use:tooltip={"Load ontology file"}>
            <input
                type="file"
                accept=".json"
                class="hidden"
                disabled={isLoading || !container}
                onchange={onInput}
            />
            <FileInput
                class="size-6 text-neutral-300 group-hover:text-neutral-600 hover:text-neutral-900 transition active:scale-95"
            />
        </label>
        <div class="grow"></div>
    </footer>

    <!-- Full-screen graph container -->
    <div class="h-svh w-svw" bind:this={container}></div>

    {#if !sigma}
        <div class="absolute inset-0 flex items-stretch">
            <label class="cursor-pointer grow grid place-items-center">
                <input
                    type="file"
                    accept=".json"
                    class="hidden"
                    disabled={isLoading || !container}
                    onchange={onInput}
                />
                <div class="text-center">
                    <FileInput class="size-12 mx-auto text-neutral-400 mb-4" />
                    <p class="text-lg text-neutral-600 mb-2">
                        Load an ontology-hydra export file to visualize
                    </p>
                </div></label
            >
        </div>
    {/if}

    {#if isLoading}
        <div class="absolute inset-0 z-20 grid place-items-center bg-white/80">
            <p class="font-semibold text-slate-800">Loading…</p>
        </div>
    {/if}

    {#if error}
        <p
            class="absolute bottom-4 left-4 z-10 rounded-lg px-4 py-3 text-sm text-red-700 bg-red-50 border border-red-200 shadow-lg"
        >
            {error}
        </p>
    {/if}
</main>
