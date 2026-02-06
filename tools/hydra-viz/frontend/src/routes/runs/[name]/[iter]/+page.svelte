<script lang="ts">
	import Histogram from '$lib/components/charts/Histogram.svelte'
	import MetricCard from '$lib/components/charts/MetricCard.svelte'
	import { coverage } from '$lib/utils/format'
	import type { PageData } from './$types'

	let { data }: { data: PageData } = $props()

	const m = $derived(data.run.iterations[data.iterNum]?.ontology_metrics ?? null)
	const prev = $derived(
		data.iterNum > 0 ? data.run.iterations[data.iterNum - 1]?.ontology_metrics ?? null : null
	)
</script>

<div class="mx-auto w-full max-w-6xl space-y-8 px-4 py-8">
	{#if m}
		<section>
			<h2 class="mb-4 text-sm font-medium text-muted">Overview</h2>
			<div class="grid grid-cols-2 gap-4 sm:grid-cols-3">
				<MetricCard
					value={m.counts.n_classes}
					label="classes"
					previous={prev?.counts.n_classes}
				/>
				<MetricCard
					value={m.distributions.class_depth.max}
					label="max depth"
					previous={prev?.distributions.class_depth.max}
				/>
				<MetricCard
					value="{Math.round(coverage(m) * 100)}%"
					label="coverage"
					current={coverage(m)}
					previous={prev ? coverage(prev) : undefined}
				/>
			</div>
		</section>

		<section>
			<h2 class="mb-4 text-sm font-medium text-muted">Properties</h2>
			<div class="grid grid-cols-2 gap-4">
				<MetricCard
					value={m.counts.n_data_properties}
					label="data properties"
					previous={prev?.counts.n_data_properties}
				/>
				<MetricCard
					value={m.counts.n_object_properties}
					label="object properties"
					previous={prev?.counts.n_object_properties}
				/>
			</div>
		</section>

		<section class="space-y-4">
			<h2 class="text-sm font-medium text-muted">Distributions</h2>
			<div class="grid gap-4 md:grid-cols-2">
				<Histogram title="Class Depth" metric={m.distributions.class_depth} />
				<Histogram title="Subclasses / Class" metric={m.distributions.subclasses_per_class} />
				<Histogram title="Data Props / Class" metric={m.distributions.data_props_per_class} />
				<Histogram title="Object Props Out / Class" metric={m.distributions.object_props_out_per_class} />
			</div>
		</section>
	{:else}
		<div class="border border-edge p-8 text-center text-muted">
			No metrics available for this iteration
		</div>
	{/if}
</div>
