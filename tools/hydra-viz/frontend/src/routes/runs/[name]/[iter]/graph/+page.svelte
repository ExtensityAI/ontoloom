<script lang="ts">
  import OntologyGraph from "$lib/components/OntologyGraph.svelte"
  import { computeOntologyDiff, type OntologyDiff } from "$lib/utils/diff"
  import type { PageData } from "./$types"

  let { data }: { data: PageData } = $props()

  const iteration = $derived(data.iteration)
  const previousIteration = $derived(data.previousIteration)

  const diff = $derived.by((): OntologyDiff | undefined => {
    if (!iteration?.ontology) return undefined
    if (data.iterNum === 0) return undefined
    return computeOntologyDiff(previousIteration?.ontology ?? null, iteration.ontology)
  })
</script>

<div class="space-y-4">
  <h1 class="text-base font-semibold text-fg">Iteration {data.iterNum} Graph</h1>

  <div class="h-[calc(100vh-14rem)] rounded-xl border border-edge bg-surface/70 overflow-hidden">
    <OntologyGraph ontology={iteration?.ontology ?? null} {diff} />
  </div>
</div>
