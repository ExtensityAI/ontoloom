<script lang="ts">
    import { onDestroy } from "svelte"
    import Sigma from "sigma"
    import Graph from "graphology"
    import { parse as parseGraphML } from "graphology-graphml/browser"
    import forceAtlas2, { inferSettings } from "graphology-layout-forceatlas2"
    import { ontologyExportSchema, type OntologyExport } from "../lib/schema"

    let isLoading = $state(false)
    let error = $state("")
    let fileName = $state("")

    let container: HTMLDivElement | undefined = $state()
    let sigma: Sigma | null = null

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

    const buildGraphFromExport = (data: OntologyExport) => {
        const graph = new Graph({ multi: true })

        const ensureNode = (id: string, attrs: Record<string, unknown>) => {
            if (!graph.hasNode(id)) graph.addNode(id, attrs)
        }

        const edges = new Set<string>()
        const addEdge = (
            source: string,
            target: string,
            attrs: Record<string, unknown>,
        ) => {
            const key = `${source}->${target}:${attrs.label ?? ""}:${attrs.type ?? ""}`
            if (edges.has(key)) return
            edges.add(key)
            graph.addEdge(source, target, attrs)
        }

        const classId = (name: string) => `class:${name}`
        const datatypeId = (name: string) => `datatype:${name}`

        // classes
        data.classes.forEach(({ data: cls }) => {
            ensureNode(classId(cls.name), {
                label: cls.name,
                type_: "class",
                color: "#0f172a",
                size: 10,
            })
        })

        // hierarchy edges using children
        data.classes.forEach(({ data: cls, children }) => {
            children.forEach((child) => {
                ensureNode(classId(child), {
                    label: child,
                    type_: "class",
                    color: "#0f172a",
                    size: 10,
                })
                addEdge(classId(cls.name), classId(child), {
                    label: "inherits",
                    type_: "hierarchy",
                    color: "#94a3b8",
                })
            })
        })

        // properties
        data.properties.forEach((prop) => {
            if (prop.type === "data") {
                prop.data.domain.forEach((domain) => {
                    ensureNode(classId(domain), {
                        label: domain,
                        type_: "class",
                        color: "#0f172a",
                        size: 10,
                    })
                    ensureNode(datatypeId(prop.data.range), {
                        label: prop.data.range,
                        type_: "datatype",
                        color: "#0369a1",
                        size: 7,
                    })
                    addEdge(classId(domain), datatypeId(prop.data.range), {
                        label: prop.data.name,
                        type_: "data",
                        color: "#0ea5e9",
                    })
                })
            } else {
                prop.data.domain.forEach((domain) => {
                    prop.data.range.forEach((target) => {
                        ensureNode(classId(domain), {
                            label: domain,
                            type_: "class",
                            color: "#0f172a",
                            size: 10,
                        })
                        ensureNode(classId(target), {
                            label: target,
                            type_: "class",
                            color: "#0f172a",
                            size: 10,
                        })
                        addEdge(classId(domain), classId(target), {
                            label: prop.data.name,
                            type_: "object",
                            color: "#f97316",
                        })
                    })
                })
            }
        })

        return graph
    }

    const load = async (file: File) => {
        isLoading = true
        error = ""
        try {
            const content = await file.text()
            const lower = file.name.toLowerCase()
            const G =
                lower.endsWith(".json") || lower.endsWith(".jsonc")
                    ? buildGraphFromExport(
                          ontologyExportSchema.parse(JSON.parse(content)),
                      )
                    : parseGraphML(Graph, content)

            // compute initial positions
            ensurePositions(G)

            // run ForceAtlas2 to layout the graph
            forceAtlas2.assign(G, {
                iterations: 1000,
                settings: inferSettings(G),
            })

            // destroy previous instance
            sigma?.kill()

            sigma = new Sigma(G, container!, {
                renderLabels: true,
                renderEdgeLabels: true,

                nodeReducer: (node, data) => ({
                    ...data,
                }),
                edgeReducer: (edge, data) => ({
                    ...data,
                }),
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

<main class="relative min-h-screen bg-slate-100">
    <header
        class="absolute top-4 left-4 z-10 flex items-center gap-4 rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-lg"
    >
        <div>
            {#if fileName}
                <p
                    class="text-xs uppercase tracking-widest font-semibold text-slate-500"
                >
                    GraphML Viewer
                </p>
            {/if}
            <p class="font-semibold text-slate-900">
                {fileName || "GraphML Viewer"}
            </p>
            <p class="text-sm text-slate-600">
                {#if isLoading}
                    Loading…
                {:else}
                    Drop a file or click to load
                {/if}
            </p>
        </div>

        <label
            class="cursor-pointer rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-semibold hover:shadow whitespace-nowrap"
        >
            <input
                type="file"
                accept=".graphml,.xml,.json"
                class="hidden"
                disabled={isLoading || !container}
                onchange={onInput}
            />
            {fileName ? "Load another" : "Choose file"}
        </label>
    </header>

    <!-- Full-screen graph container -->
    <div class="absolute inset-0" bind:this={container}></div>

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
