<script lang="ts">
  import RunHeader from "$lib/components/runs/RunHeader.svelte"
  import type { LayoutData } from "./$types"

  let { data, children }: { data: LayoutData; children: any } = $props()
</script>

<RunHeader run={data.run} />
{@render children()}
