<script lang="ts">
    import { onDestroy } from "svelte"
    import Sigma from "sigma"
    import FA2Layout from "graphology-layout-forceatlas2/worker"
    import { inferSettings } from "graphology-layout-forceatlas2"
    import {
        FileInput as FileInputIcon,
        SquareIcon,
        LoaderCircleIcon,
    } from "lucide-svelte/icons"
    import { tooltip } from "./lib/ui/tooltip"
    import { ontologySchema } from "./lib/graph/schema"
    import {
        createOntologyGraph,
        initializeNodePositions,
    } from "./lib/graph/parser"
    import {
        createEdgeReducer,
        createNodeReducer,
    } from "./lib/visualizer/reducers"
    import {
        createSelection,
        emptySelection,
        getActiveSelection as getActiveSelectionFromState,
    } from "./lib/visualizer/selection"
    import type { RuntimeState, ViewState } from "./lib/visualizer/types"

    // ─── State ───────────────────────────────────────────────────────────────────

    const FILE_ACCEPT = ".json"

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

    const isFileInputDisabled = $derived(runtimeState.isLoading || !container)

    // Active selection: pinned takes priority over hovered
    const getActiveSelection = () => getActiveSelectionFromState(viewState)
    const nodeReducer = createNodeReducer(getActiveSelection)
    const edgeReducer = createEdgeReducer(getActiveSelection)

    // ─── Event Handlers ──────────────────────────────────────────────────────────

    const refreshSigma = () => {
        runtimeState.sigma?.refresh()
    }

    const setHovered = (node: string | null) => {
        viewState.hovered = createSelection(node, runtimeState.graph)
        refreshSigma()
    }

    const setPinned = (node: string | null) => {
        // Toggle: if clicking the same node, unpin; otherwise pin the new node
        const newNode = viewState.pinned.node === node ? null : node
        viewState.pinned = createSelection(newNode, runtimeState.graph)
        refreshSigma()
    }

    const clearPinned = () => {
        if (viewState.pinned.node) {
            viewState.pinned = emptySelection()
            refreshSigma()
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
                accept={FILE_ACCEPT}
                disabled={isFileInputDisabled}
                onchange={handleInputChange}
            />
            <FileInputIcon
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
                        hidden
                        class="hidden"
                        accept={FILE_ACCEPT}
                        disabled={isFileInputDisabled}
                        onchange={handleInputChange}
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

    {#if runtimeState.error}
        <p
            class="absolute bottom-4 left-4 z-10 rounded-lg px-4 py-3 text-sm text-red-700 bg-red-50 border border-red-200 shadow-lg"
        >
            {runtimeState.error}
        </p>
    {/if}
</main>
