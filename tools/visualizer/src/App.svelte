<script lang="ts">
    import { onDestroy, tick } from "svelte"
    import Sigma from "sigma"
    import FA2Layout from "graphology-layout-forceatlas2/worker"
    import {
        FileInput as FileInputIcon,
        SquareIcon,
        LoaderCircleIcon,
        SearchIcon,
    } from "lucide-svelte/icons"
    import { tooltip } from "./lib/ui/tooltip"
    import { ontologySchema } from "./lib/graph/schema"
    import { createOntologyGraph } from "./lib/graph/parser"
    import {
        createEdgeReducer,
        createNodeReducer,
    } from "./lib/visualizer/reducers"
    import { createSelection } from "./lib/visualizer/selection"
    import type { RuntimeState, ViewState } from "./lib/visualizer/types"
    import { inferSettings } from "graphology-layout-forceatlas2"
    import NodeSearch from "./lib/ui/NodeSearch.svelte"
    import { scale } from "svelte/transition"

    // ─── State ───────────────────────────────────────────────────────────────────

    let container: HTMLDivElement | null = $state(null)
    let searchInput: HTMLInputElement | null = $state(null)

    let runtimeState: RuntimeState = $state({
        isLoading: false,
        isLayoutRunning: false,
        fileName: "",
        sigma: null,
        graph: null,
        layout: null,
    })

    let viewState: ViewState = $state({
        hoveredNode: null,
        pinnedNode: null,
        searchVisible: false,
    })

    const isFileInputDisabled = $derived(runtimeState.isLoading || !container)

    const hoveredSelection = $derived(
        viewState.hoveredNode && runtimeState.graph
            ? createSelection(viewState.hoveredNode, runtimeState.graph)
            : null,
    )
    const pinnedSelection = $derived(
        viewState.pinnedNode && runtimeState.graph
            ? createSelection(viewState.pinnedNode, runtimeState.graph)
            : null,
    )
    const activeSelection = $derived(
        viewState.pinnedNode ? pinnedSelection : hoveredSelection,
    )

    const nodeReducer = createNodeReducer(() => activeSelection)
    const edgeReducer = createEdgeReducer(() => activeSelection)

    // ─── Event Handlers ──────────────────────────────────────────────────────────

    let refreshQueued = false
    const refreshSigma = async () => {
        if (refreshQueued) return
        refreshQueued = true
        await tick()
        refreshQueued = false
        runtimeState.sigma?.refresh()
    }

    const setHovered = (node: string | null) => {
        viewState.hoveredNode = node
        refreshSigma()
    }

    const setPinned = (node: string | null) => {
        // Toggle: if clicking the same node, unpin; otherwise pin the new node
        const newNode = viewState.pinnedNode === node ? null : node
        viewState.pinnedNode = newNode
        refreshSigma()
    }

    // ─── Layout Control ──────────────────────────────────────────────────────────

    const stopLayout = () => {
        runtimeState.layout?.stop()
        runtimeState.layout?.kill()
        runtimeState.layout = null
        runtimeState.isLayoutRunning = false
    }

    const destroySigma = () => {
        stopLayout()

        runtimeState.sigma?.kill()
        runtimeState.sigma = null
        runtimeState.graph = null
    }

    // ─── File Loading with Live Layout ───────────────────────────────────────────

    const handleFileLoad = async (file: File) => {
        if (runtimeState.isLoading || !container) return

        runtimeState.isLoading = true
        runtimeState.fileName = file.name

        try {
            const content = await file.text()
            const parsed = ontologySchema.parse(JSON.parse(content))
            const graph = createOntologyGraph(parsed)

            // Clean up previous instances
            destroySigma()

            // Initialize Sigma immediately — graph appears right away
            const sigma = new Sigma(graph, container, {
                renderLabels: true,
                renderEdgeLabels: true,
                zIndex: true,
                nodeReducer,
                edgeReducer,
            })

            sigma.on("enterNode", ({ node }) => setHovered(node))
            sigma.on("leaveNode", () => setHovered(null))
            sigma.on("clickNode", ({ node }) => setPinned(node))
            sigma.on("clickStage", () => setPinned(null))

            runtimeState.sigma = sigma
            runtimeState.graph = graph

            // Start live force-directed layout in web worker
            const layout = new FA2Layout(graph, {
                settings: inferSettings(graph),
                getEdgeWeight: "weight",
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
        } finally {
            runtimeState.isLoading = false
        }
    }

    const handleFileInputChange = (e: Event) => {
        const input = e.target as HTMLInputElement
        const file = input.files?.[0]
        if (file) handleFileLoad(file)
        input.value = ""
    }

    const handleNodeSelect = (nodeId: string) => {
        if (!runtimeState.sigma) return

        viewState.searchVisible = false
        setPinned(nodeId)
    }

    const openSearch = () => {
        if (!runtimeState.sigma) return

        viewState.searchVisible = true
        setTimeout(() => {
            searchInput?.focus()
        }, 10)
    }

    // ─── Lifecycle ───────────────────────────────────────────────────────────────

    onDestroy(() => {
        destroySigma()
    })

    // ─── Keyboard Shortcuts ─────────────────────────────────────────────────────

    const handleKeyboardShortcut = async (e: KeyboardEvent) => {
        if (!runtimeState.sigma) return

        if (e.key === "/") {
            e.preventDefault()
            openSearch()
        } else if (e.key === "Escape") {
            if (viewState.searchVisible) {
                viewState.searchVisible = false
                e.preventDefault()
            }
        }
    }
</script>

<main class="relative min-h-screen">
    <footer
        class="absolute bottom-0 left-0 right-0 z-40 p-2 flex group hover:bg-white/50 hover:backdrop-blur-md transition hover:border-t-neutral-200 border-t border-t-transparent items-center"
    >
        <label class="cursor-pointer p-1" use:tooltip={"Load ontology file"}>
            <input
                type="file"
                hidden
                class="hidden"
                accept={".json"}
                disabled={isFileInputDisabled}
                onchange={handleFileInputChange}
            />
            <FileInputIcon
                class="size-6 text-neutral-300 group-hover:text-neutral-600 hover:text-neutral-900 transition active:scale-95"
            />
        </label>

        {#if runtimeState.sigma}
            <button
                class="cursor-pointer p-1"
                use:tooltip={"[ / ] Search for node"}
                onclick={openSearch}
            >
                <SearchIcon
                    class="size-6 text-neutral-300 group-hover:text-neutral-600 hover:text-neutral-900 transition active:scale-95"
                />
            </button>
        {/if}

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
        {#if activeSelection}
            <div class="text-sm text-neutral-700">
                {activeSelection.attrs.label}
            </div>
        {/if}
    </footer>

    <div class="h-svh w-svw" bind:this={container}></div>

    {#if !runtimeState.sigma}
        <div class="absolute inset-0 flex items-stretch">
            {#if !runtimeState.isLoading}
                <label class="cursor-pointer grow grid place-items-center">
                    <input
                        type="file"
                        hidden
                        class="hidden"
                        accept=".json"
                        disabled={isFileInputDisabled}
                        onchange={handleFileInputChange}
                    />
                    <div class="text-center">
                        <FileInputIcon
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

    {#if viewState.searchVisible}
        <!-- search action bar -->
        <div
            class="absolute top-96 left-1/2 -translate-x-1/2 z-50"
            transition:scale={{ duration: 50 }}
        >
            <NodeSearch
                bind:searchInput
                onSelect={handleNodeSelect}
                graph={runtimeState.graph!}
            />
        </div>
    {/if}
</main>

<svelte:window onkeydown={handleKeyboardShortcut} />
