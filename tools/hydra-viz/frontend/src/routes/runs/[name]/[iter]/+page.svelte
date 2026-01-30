<script lang="ts">
	import MetricCard from '$lib/components/MetricCard.svelte'
	import type { PageData } from './$types'

	let { data }: { data: PageData } = $props()

	const iteration = $derived(data.iteration)
	const prev = $derived(data.previousIteration?.metrics)
	const m = $derived(iteration?.metrics)
</script>

<div class="mx-auto w-full max-w-6xl space-y-8 px-4 py-8">
	{#if m}
		<section>
			<h2 class="mb-4 text-sm font-medium text-muted">Overview</h2>
			<div class="grid grid-cols-2 gap-4 sm:grid-cols-3">
				<MetricCard
					value={m.class_count}
					label="classes"
					current={m.class_count}
					previous={prev?.class_count}
				/>
				<MetricCard
					value={m.max_depth}
					label="max depth"
					current={m.max_depth}
					previous={prev?.max_depth}
				/>
				<MetricCard value="{Math.round(m.property_coverage * 100)}%" label="coverage" />
			</div>
		</section>

		<section>
			<h2 class="mb-4 text-sm font-medium text-muted">Properties</h2>
			<div class="grid grid-cols-2 gap-4">
				<MetricCard
					value={m.data_property_count}
					label="data properties"
					current={m.data_property_count}
					previous={prev?.data_property_count}
				/>
				<MetricCard
					value={m.object_property_count}
					label="object properties"
					current={m.object_property_count}
					previous={prev?.object_property_count}
				/>
			</div>
		</section>

		<section>
			<h2 class="mb-4 text-sm font-medium text-muted">Hierarchy</h2>
			<div class="grid grid-cols-2 gap-4 sm:grid-cols-4">
				<MetricCard value={m.root_class_count} label="roots" size="small" />
				<MetricCard value={m.leaf_class_count} label="leaves" size="small" />
				<MetricCard
					value={m.orphan_class_count}
					label="orphans"
					current={m.orphan_class_count}
					previous={prev?.orphan_class_count}
					invert
					size="small"
				/>
				<MetricCard value={m.avg_branching_factor.toFixed(1)} label="avg branching" size="small" />
			</div>
		</section>
	{:else}
		<div class="border border-edge p-8 text-center text-muted">
			No metrics available for this iteration
		</div>
	{/if}
</div>
