<script lang="ts">
    import type { HydraGraph } from "../graph/types"

    let {
        searchInput = $bindable<HTMLInputElement | null>(null),
        onSelect,
        graph,
    }: {
        searchInput?: HTMLInputElement | null
        onSelect: (nodeId: string) => void
        graph: HydraGraph
    } = $props()

    let options: string[] = $state([])

    const onKeyDown = (e: KeyboardEvent) => {
        if (!searchInput) return

        if (e.key === "Enter" && options.length > 0) {
            onSelect(options[0])
            return
        }

        const query = searchInput.value.toLowerCase().trim()

        if (!query) {
            options = graph.nodes()
            return
        }

        // find all nodes with matching name
        const nodes = graph
            .nodes()
            .filter((node) => node.toLowerCase().includes(query))

        options = nodes
    }
</script>

<div
    class="bg-white/50 backdrop-blur-md border-neutral-300 border rounded-lg w-96 shadow-lg"
>
    <input
        bind:this={searchInput}
        type="text"
        placeholder="Search for node..."
        class="px-4 py-2 rounded-lg w-full"
        onkeydown={onKeyDown}
    />

    <div class="max-h-72 overflow-y-auto rounded-b-lg overflow-clip">
        {#each options || graph.nodes() as option}
            <div class="px-4 py-2 cursor-pointer first:underline">
                {option}
            </div>
        {/each}
    </div>
</div>
