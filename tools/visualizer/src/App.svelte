<script lang="ts">
    import { onDestroy } from "svelte"
    import Sigma from "sigma"
    import Graph from "graphology"
    import FA2Layout from "graphology-layout-forceatlas2/worker"
    import { inferSettings } from "graphology-layout-forceatlas2"
    import {
        FileInput,
        SquareIcon,
        LoaderCircleIcon,
    } from "lucide-svelte/icons"
    import { tooltip } from "./lib/utils/tooltip"
    import { ontologySchema } from "./lib/graph/schema"
    import {
        createOntologyGraph,
        initializeNodePositions,
    } from "./lib/graph/parser"

    // ─── Constants ───────────────────────────────────────────────────────────────

    const LEVEL_COLORS = [
        "#ec003f", // rose-500 (root)
        "#fd9a00", // amber-500
        "#7ccf00", // lime-500
        "#22c55e", // green-500
        "#14b8a6", // teal-500
        "#3b82f6", // blue-500
        "#8b5cf6", // violet-500
        "#ec4899", // pink-500
        "#64748b", // slate-500
    ] as const

    const COLORS = {
        node: {
            inactive: "#e5e5e5",
            selected: "#dc2626", // red
            parent: "#f97316", // orange
            child: "#22c55e", // green
        },
        edge: {
            hierarchy: {
                default: "#e5e5e5",
                active: "#a3a3a3",
                inactive: "#f5f5f5",
            },
            property: {
                default: "#f87171",
                active: "#dc2626",
                inactive: "#fecaca",
            },
        },
    } as const

    const BASE_NODE_SIZE = 8
    const NODE_SIZE_MULTIPLIER = 4
    const ACTIVE_EDGE_SIZE = 3

    // ─── Types ───────────────────────────────────────────────────────────────────

    interface NodeSelection {
        node: string | null
        parents: Set<string>
        children: Set<string>
        connectedEdges: Set<string>
    }

    interface ViewState {
        hovered: NodeSelection
        pinned: NodeSelection
    }

    interface RuntimeState {
        isLoading: boolean
        isLayoutRunning: boolean
        error: string
        fileName: string
        sigma: Sigma | null
        graph: Graph | null
        layout: FA2Layout | null
    }

    // ─── Helpers ─────────────────────────────────────────────────────────────────

    const emptySelection = (): NodeSelection => ({
        node: null,
        parents: new Set(),
        children: new Set(),
        connectedEdges: new Set(),
    })

    const createSelection = (
        node: string | null,
        graph: Graph | null,
    ): NodeSelection => {
        if (!node || !graph) return emptySelection()

        const attrs = graph.getNodeAttributes(node)
        return {
            node,
            parents: attrs.parents as Set<string>,
            children: attrs.children as Set<string>,
            connectedEdges: attrs.edges as Set<string>,
        }
    }

    // ─── State ───────────────────────────────────────────────────────────────────

    let container: HTMLDivElement | undefined = $state()

    let runtimeState: RuntimeState = $state({
        isLoading: false,
        isLayoutRunning: false,
        error: "",
        fileName: "",
        sigma: null,
        graph: null,
        layout: null,
    })

    let viewState: ViewState = $state({
        hovered: emptySelection(),
        pinned: emptySelection(),
    })

    // Active selection: pinned takes priority over hovered
    const getActiveSelection = (): NodeSelection =>
        viewState.pinned.node ? viewState.pinned : viewState.hovered

    // ─── Reducers ────────────────────────────────────────────────────────────────

    const nodeReducer = (node: string, data: Record<string, unknown>) => {
        const active = getActiveSelection()
        const isSelected = active.node === node
        const isParent = active.parents.has(node)
        const isChild = active.children.has(node)
        const isRelated = isSelected || isParent || isChild
        const hasSelection = active.node !== null

        let color: string
        if (isSelected) {
            color = COLORS.node.selected
        } else if (isParent) {
            color = COLORS.node.parent
        } else if (isChild) {
            color = COLORS.node.child
        } else if (hasSelection) {
            color = COLORS.node.inactive
        } else {
            color = LEVEL_COLORS[data.level as number] ?? LEVEL_COLORS.at(-1)!
        }

        return {
            ...data,
            color,
            size:
                BASE_NODE_SIZE +
                (data.inverseLevel as number) * NODE_SIZE_MULTIPLIER,
            zIndex: isSelected ? 2 : isRelated ? 1 : 0,
        }
    }

    const edgeReducer = (edge: string, data: Record<string, unknown>) => {
        const active = getActiveSelection()
        const isConnected = active.connectedEdges.has(edge)
        const hasSelection = active.node !== null
        const isHierarchy = data.tag === "hierarchy"

        const palette = isHierarchy
            ? COLORS.edge.hierarchy
            : COLORS.edge.property
        const color = hasSelection
            ? isConnected
                ? palette.active
                : palette.inactive
            : palette.default

        const showLabel =
            data.source === active.node || data.target === active.node

        return {
            ...data,
            color,
            size: isConnected ? ACTIVE_EDGE_SIZE : (data.size as number),
            zIndex: isConnected ? 1 : 0,
            label: showLabel ? (data.label as string) : "",
        }
    }

    // ─── Event Handlers ──────────────────────────────────────────────────────────

    const setHovered = (node: string | null) => {
        viewState.hovered = createSelection(node, runtimeState.graph)
        runtimeState.sigma?.refresh()
    }

    const setPinned = (node: string | null) => {
        // Toggle: if clicking the same node, unpin; otherwise pin the new node
        const newNode = viewState.pinned.node === node ? null : node
        viewState.pinned = createSelection(newNode, runtimeState.graph)
        runtimeState.sigma?.refresh()
    }

    const clearPinned = () => {
        if (viewState.pinned.node) {
            viewState.pinned = emptySelection()
            runtimeState.sigma?.refresh()
        }
    }

    // ─── Layout Control ──────────────────────────────────────────────────────────

    const stopLayout = () => {
        if (runtimeState.layout) {
            runtimeState.layout.stop()
            runtimeState.layout.kill()
            runtimeState.layout = null
            runtimeState.isLayoutRunning = false
        }
    }

    // ─── File Loading with Live Layout ───────────────────────────────────────────

    const handleFileLoad = async (file: File) => {
        if (runtimeState.isLoading) return

        runtimeState.isLoading = true
        runtimeState.error = ""
        runtimeState.fileName = file.name

        try {
            const content = await file.text()
            const parsed = ontologySchema.parse(JSON.parse(content))
            const graph = createOntologyGraph(parsed)

            // Initialize positions before layout
            initializeNodePositions(graph)

            // Clean up previous instances
            stopLayout()
            runtimeState.sigma?.kill()

            // Initialize Sigma immediately — graph appears right away
            const sigma = new Sigma(graph, container!, {
                renderLabels: true,
                renderEdgeLabels: true,
                nodeReducer,
                edgeReducer,
            })

            sigma.on("enterNode", ({ node }) => setHovered(node))
            sigma.on("leaveNode", () => setHovered(null))
            sigma.on("clickNode", ({ node }) => setPinned(node))
            sigma.on("clickStage", () => clearPinned())

            runtimeState.sigma = sigma
            runtimeState.graph = graph

            // Start live force-directed layout in web worker
            const layout = new FA2Layout(graph, {
                settings: inferSettings(graph),
            })
            layout.start()
            runtimeState.layout = layout
            runtimeState.isLayoutRunning = true

            // Auto-stop after 10 seconds (usually converged by then)
            setTimeout(() => {
                if (runtimeState.layout === layout) {
                    stopLayout()
                }
            }, 10_000)
        } catch (e) {
            console.error(e)
            runtimeState.error =
                e instanceof Error
                    ? e.message
                    : typeof e === "string"
                      ? e
                      : "Failed to load file"
        } finally {
            runtimeState.isLoading = false
        }
    }

    const handleInputChange = (e: Event) => {
        const input = e.target as HTMLInputElement
        const file = input.files?.[0]
        if (file) handleFileLoad(file)
        input.value = ""
    }

    // ─── Lifecycle ───────────────────────────────────────────────────────────────

    onDestroy(() => {
        stopLayout()
        runtimeState.sigma?.kill()
    })
</script>

<main class="relative min-h-screen">
    <footer class="absolute bottom-0 left-0 right-0 z-100 p-2 flex group">
        <label class="cursor-pointer p-1" use:tooltip={"Load ontology file"}>
            <input
                type="file"
                accept=".json"
                class="hidden"
                disabled={runtimeState.isLoading || !container}
                onchange={handleInputChange}
            />
            <FileInput
                class="size-6 text-neutral-300 group-hover:text-neutral-600 hover:text-neutral-900 transition active:scale-95"
            />
        </label>

        {#if runtimeState.isLayoutRunning}
            <button
                class="cursor-pointer p-1"
                use:tooltip={"Stop layout"}
                onclick={stopLayout}
            >
                <SquareIcon
                    class="size-6 text-neutral-300 group-hover:text-neutral-600 hover:text-neutral-900 transition active:scale-95"
                />
            </button>
        {/if}

        <div class="grow"></div>
    </footer>

    <div class="h-svh w-svw" bind:this={container}></div>

    {#if !runtimeState.sigma}
        <div class="absolute inset-0 flex items-stretch">
            {#if !runtimeState.isLoading}
                <label class="cursor-pointer grow grid place-items-center">
                    <input
                        type="file"
                        accept=".json"
                        class="hidden"
                        disabled={runtimeState.isLoading || !container}
                        onchange={handleInputChange}
                    />
                    <div class="text-center">
                        <FileInput
                            class="size-12 mx-auto text-neutral-400 mb-4"
                        />
                        <p class="text-lg text-neutral-600">
                            Load an ontology-hydra export .json file to
                            visualize
                        </p>
                    </div>
                </label>
            {:else}
                <div class="grow grid place-items-center">
                    <div>
                        <LoaderCircleIcon
                            class="size-12 mx-auto text-neutral-400 mb-4 animate-spin"
                        />
                        <p class="text-lg text-neutral-600">
                            Loading {runtimeState.fileName}…
                        </p>
                    </div>
                </div>
            {/if}
        </div>
    {/if}

    {#if runtimeState.error}
        <p
            class="absolute bottom-4 left-4 z-10 rounded-lg px-4 py-3 text-sm text-red-700 bg-red-50 border border-red-200 shadow-lg"
        >
            {runtimeState.error}
        </p>
    {/if}
</main>
