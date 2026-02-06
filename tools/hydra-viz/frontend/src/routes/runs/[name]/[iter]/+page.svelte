<script lang="ts">
	import Histogram from "$lib/components/charts/Histogram.svelte"
	import { computeDelta } from "$lib/utils/delta"
	import { coverage } from "$lib/utils/format"
	import type { PageData } from "./$types"

	let { data }: { data: PageData } = $props()

	const m = $derived(data.run.iterations[data.iterNum]?.ontology_metrics ?? null)
	const prev = $derived(
		data.iterNum > 0 ? data.run.iterations[data.iterNum - 1]?.ontology_metrics ?? null : null
	)

	const buildTile = (
		label: string,
		value: string | number,
		curr: number | undefined,
		previous: number | undefined,
		accent: string,
		suffix = "",
		digits?: number
	) => {
		if (digits === undefined) {
			const delta = computeDelta(curr, previous)
			const deltaText = delta.text ? `${delta.text}${suffix}` : "—"
			return {
				label,
				value,
				accent,
				deltaText,
				deltaColor: delta.text ? delta.color : "text-faint"
			}
		}

		if (curr === undefined || previous === undefined) {
			return {
				label,
				value,
				accent,
				deltaText: "—",
				deltaColor: "text-faint"
			}
		}

		const raw = Number((curr - previous).toFixed(digits))
		if (raw === 0) {
			return {
				label,
				value,
				accent,
				deltaText: "—",
				deltaColor: "text-faint"
			}
		}

		const sign = raw > 0 ? "+" : ""
		const deltaText = `${sign}${raw.toFixed(digits)}${suffix}`
		return {
			label,
			value,
			accent,
			deltaText,
			deltaColor: raw > 0 ? "text-ok" : "text-err"
		}
	}

	const overviewTiles = $derived.by(() => {
		if (!m) return []
		const coverageNow = Number((coverage(m) * 100).toFixed(1))
		const coveragePrev = prev ? Number((coverage(prev) * 100).toFixed(1)) : undefined
		return [
			buildTile(
				"classes",
				m.counts.n_classes,
				m.counts.n_classes,
				prev?.counts.n_classes,
				"bg-metric-classes"
			),
			buildTile(
				"max depth",
				m.distributions.class_depth.max,
				m.distributions.class_depth.max,
				prev?.distributions.class_depth.max,
				"bg-metric-depth"
			),
			buildTile(
				"coverage",
				`${coverageNow}%`,
				coverageNow,
				coveragePrev,
				"bg-metric-coverage",
				"pp",
				1
			)
		]
	})

	const propertyTiles = $derived.by(() => {
		if (!m) return []
		return [
			buildTile(
				"data properties",
				m.counts.n_data_properties,
				m.counts.n_data_properties,
				prev?.counts.n_data_properties,
				"bg-metric-properties"
			),
			buildTile(
				"object properties",
				m.counts.n_object_properties,
				m.counts.n_object_properties,
				prev?.counts.n_object_properties,
				"bg-metric-properties"
			)
		]
	})
</script>

<div class="mx-auto w-full max-w-6xl space-y-8 px-4 py-8">
	{#if m}
		<section>
			<h2 class="mb-4 text-sm font-medium text-muted">Overview</h2>
			<div class="grid grid-cols-2 gap-4 sm:grid-cols-3">
				{#each overviewTiles as tile}
					<div class="relative overflow-hidden rounded border border-edge bg-surface/30 p-3">
						<div class={`absolute inset-x-0 top-0 h-0.5 ${tile.accent}`}></div>
						<div class="text-xs text-muted">{tile.label}</div>
						<div class="font-mono text-lg">{tile.value}</div>
						<div class={`text-xs ${tile.deltaColor}`}>Δ {tile.deltaText}</div>
					</div>
				{/each}
			</div>
		</section>

		<section>
			<h2 class="mb-4 text-sm font-medium text-muted">Properties</h2>
			<div class="grid grid-cols-2 gap-4">
				{#each propertyTiles as tile}
					<div class="relative overflow-hidden rounded border border-edge bg-surface/30 p-3">
						<div class={`absolute inset-x-0 top-0 h-0.5 ${tile.accent}`}></div>
						<div class="text-xs text-muted">{tile.label}</div>
						<div class="font-mono text-lg">{tile.value}</div>
						<div class={`text-xs ${tile.deltaColor}`}>Δ {tile.deltaText}</div>
					</div>
				{/each}
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
