<script lang="ts">
  import OntologyGraph from "$lib/components/graph/OntologyGraph.svelte"
  import type { PageData } from "./$types"

  let { data }: { data: PageData } = $props()

  const iteration = $derived(data.iteration)
</script>

<OntologyGraph ontology={iteration?.ontology ?? null} />
