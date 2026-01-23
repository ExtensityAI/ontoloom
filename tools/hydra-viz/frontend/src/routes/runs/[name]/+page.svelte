<script lang="ts">
	import { page } from '$app/stores';
	import { fetchIteration } from '$lib/api/client';
	import type { IterationDetail, Ontology } from '$lib/api/types';
	import { formatDateTimeFull } from '$lib/utils/date';
	import { computeOntologyDiff, type OntologyDiff } from '$lib/utils/diff';
	import IterationSlider from '$lib/components/IterationSlider.svelte';
	import OntologyGraph from '$lib/components/OntologyGraph.svelte';
	import MetricsCharts from '$lib/components/MetricsCharts.svelte';
	import DiffSummary from '$lib/components/DiffSummary.svelte';
	import MetricCard from '$lib/components/MetricCard.svelte';
	import { ArrowLeftIcon, FileTextIcon, ClipboardListIcon, MessageSquareIcon } from '@lucide/svelte';
	import type { Component } from 'svelte';
	import type { PageData } from './$types';

	type TabId = 'plan' | 'review' | 'ops';
	const tabs: { id: TabId; label: string; icon: Component }[] = [
		{ id: 'plan', label: 'Plan', icon: FileTextIcon },
		{ id: 'review', label: 'Review', icon: MessageSquareIcon },
		{ id: 'ops', label: 'Raw Ops', icon: ClipboardListIcon }
	];

	let { data }: { data: PageData } = $props();

	let iteration = $state<IterationDetail | null>(data.iteration);
	let previousOntology = $state<Ontology | null>(null);
	let currentIdx = $state(0);
	let activeTab = $state<TabId>('plan');

	const name = $derived($page.params.name);
	const run = $derived(data.run);
	const metrics = $derived(data.metrics);

	// Compute diff between previous and current ontology
	const diff = $derived.by((): OntologyDiff | undefined => {
		if (!iteration?.ontology) return undefined;
		if (currentIdx === 0) return undefined; // No diff for first iteration
		return computeOntologyDiff(previousOntology, iteration.ontology);
	});

	// Get previous iteration metrics for comparison
	const previousMetrics = $derived.by(() => {
		if (!metrics || currentIdx === 0) return null;
		const point = metrics.points.find((p) => p.iteration === currentIdx - 1);
		return point?.metrics ?? null;
	});

	const loadIteration = async (idx: number) => {
		try {
			// Load previous iteration for diff comparison
			if (idx > 0) {
				const prevIter = await fetchIteration(name, idx - 1);
				previousOntology = prevIter.ontology;
			} else {
				previousOntology = null;
			}

			iteration = await fetchIteration(name, idx);
		} catch (e) {
			console.error('Failed to load iteration:', e);
		}
	};

	const onIterationChange = async (idx: number) => {
		currentIdx = idx;
		await loadIteration(idx);
	};

	// Helper to get display name for an operation
	const getOpDisplayName = (op: IterationDetail['ops'][number]): string => {
		if ('name' in op) return op.name;
		if ('target_name' in op) return op.target_name;
		return '';
	};

	// Helper to get operation details (excluding op and name fields)
	const getOpDetails = (op: IterationDetail['ops'][number]): Record<string, unknown> => {
		const { op: _op, name: _name, ...rest } = op as Record<string, unknown>;
		return rest;
	};

	// Group operations by type
	const groupedOps = $derived.by(() => {
		if (!iteration?.ops) return { adds: [], updates: [], deletes: [], merges: [] };
		return {
			adds: iteration.ops.filter((op) => op.op.startsWith('add')),
			updates: iteration.ops.filter((op) => op.op.startsWith('update')),
			deletes: iteration.ops.filter((op) => op.op.startsWith('del')),
			merges: iteration.ops.filter((op) => op.op === 'merge_classes')
		};
	});

	// Keyboard shortcuts for iteration navigation
	const handleKeydown = (event: KeyboardEvent) => {
		// Don't trigger if typing in an input
		if (event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement) {
			return;
		}

		if (!run || run.iterations.length <= 1) return;

		switch (event.key) {
			case 'ArrowLeft':
				if (currentIdx > 0) {
					onIterationChange(currentIdx - 1);
				}
				break;
			case 'ArrowRight':
				if (currentIdx < run.iterations.length - 1) {
					onIterationChange(currentIdx + 1);
				}
				break;
		}
	};

	$effect(() => {
		window.addEventListener('keydown', handleKeydown);
		return () => window.removeEventListener('keydown', handleKeydown);
	});
</script>

<div>
	<!-- Header -->
	<div class="flex items-center gap-4 mb-6">
		<a href="/" class="p-2 rounded-lg hover:bg-hover transition-colors" title="Back to runs list">
			<ArrowLeftIcon class="w-5 h-5" />
		</a>
		<div class="flex-1">
			<h1 class="text-xl font-bold">{name}</h1>
			{#if run}
				<p class="text-sm text-muted">
					{formatDateTimeFull(run.metadata.created_at)} · {run.iterations.length} iterations
				</p>
				{#if run.metadata.intent}
					<p class="text-xs text-faint mt-1 max-w-3xl line-clamp-2">{run.metadata.intent}</p>
				{/if}
			{/if}
		</div>
	</div>

	{#if run}
		<!-- Iteration controls row -->
		<div class="flex flex-col lg:flex-row gap-4 mb-4">
			{#if run.iterations.length > 1}
				<div class="flex-1">
					<IterationSlider
						bind:current={currentIdx}
						max={run.iterations.length - 1}
						onchange={onIterationChange}
					/>
				</div>
			{/if}

			{#if diff && currentIdx > 0}
				<DiffSummary {diff} previousIteration={currentIdx - 1} currentIteration={currentIdx} />
			{/if}
		</div>

		<!-- Main content grid: Graph left, sidebar right -->
		<div class="grid lg:grid-cols-4 gap-4">
			<!-- Left: Graph (larger) -->
			<div class="lg:col-span-3">
				<div class="h-[600px]">
					<OntologyGraph ontology={iteration?.ontology ?? null} {diff} />
				</div>

				<!-- Tabs below graph -->
				<div class="mt-4">
					<div class="flex gap-1 bg-surface rounded-lg p-1 border border-edge mb-4">
						{#each tabs as tab (tab.id)}
							<button
								type="button"
								onclick={() => (activeTab = tab.id)}
								class="flex-1 px-3 py-2 rounded-md text-sm font-medium transition-colors {activeTab ===
								tab.id
									? 'bg-hover text-fg'
									: 'text-muted hover:text-fg'}"
							>
								<tab.icon class="w-4 h-4 inline-block mr-1.5" />
								{tab.label}
								{#if tab.id === 'ops' && iteration?.ops.length}
									<span class="ml-1 text-xs bg-faint/30 px-1.5 py-0.5 rounded-full">
										{iteration.ops.length}
									</span>
								{/if}
							</button>
						{/each}
					</div>

					<!-- Tab content -->
					<div class="max-h-[400px] overflow-auto bg-surface rounded-lg border border-edge p-4">
						{#if activeTab === 'plan'}
							{#if iteration?.plan}
								<pre class="text-sm text-muted whitespace-pre-wrap font-mono">{iteration.plan}</pre>
							{:else}
								<div class="text-faint text-center py-8">No plan available</div>
							{/if}
						{:else if activeTab === 'review'}
							{#if iteration?.review}
								<pre class="text-sm text-muted whitespace-pre-wrap font-mono">{iteration.review}</pre>
							{:else}
								<div class="text-faint text-center py-8">No review available</div>
							{/if}
						{:else if activeTab === 'ops'}
							{#if iteration?.ops && iteration.ops.length > 0}
								<div class="space-y-2">
									{#each iteration.ops as op}
										<div class="bg-bg rounded p-3 border border-edge">
											<div class="flex items-center gap-2 mb-2">
												<span
													class="px-2 py-0.5 text-xs font-mono rounded {op.op.startsWith('add')
														? 'bg-ok/20 text-ok'
														: op.op.startsWith('del')
															? 'bg-err/20 text-err'
															: op.op.startsWith('update')
																? 'bg-warn/20 text-warn'
																: op.op === 'merge_classes'
																	? 'bg-info/20 text-info'
																	: 'bg-hover text-muted'}"
												>
													{op.op}
												</span>
												{#if getOpDisplayName(op)}
													<span class="font-medium">{getOpDisplayName(op)}</span>
												{/if}
											</div>
											<pre class="text-xs text-muted overflow-x-auto">{JSON.stringify(getOpDetails(op), null, 2)}</pre>
										</div>
									{/each}
								</div>
							{:else}
								<div class="text-faint text-center py-8">No operations</div>
							{/if}
						{/if}
					</div>
				</div>
			</div>

			<!-- Right: Sidebar with metrics and operations summary -->
			<div class="lg:col-span-1 space-y-4">
				<!-- Metrics cards -->
				{#if iteration?.metrics}
					<div class="bg-surface rounded-lg border border-edge p-4">
						<h3 class="text-sm font-semibold text-muted mb-3">Metrics</h3>
						<div class="space-y-3">
							<MetricCard
								label="Classes"
								value={iteration.metrics.class_count}
								previousValue={previousMetrics?.class_count}
								color="accent"
							/>
							<MetricCard
								label="Max Depth"
								value={iteration.metrics.max_depth}
								previousValue={previousMetrics?.max_depth}
								color="ok"
							/>
							<MetricCard
								label="Data Properties"
								value={iteration.metrics.data_property_count}
								previousValue={previousMetrics?.data_property_count}
								color="info"
							/>
							<MetricCard
								label="Object Properties"
								value={iteration.metrics.object_property_count}
								previousValue={previousMetrics?.object_property_count}
								color="lvl3"
							/>
							<MetricCard
								label="Coverage"
								value={Math.round(iteration.metrics.property_coverage * 100)}
								previousValue={previousMetrics ? Math.round(previousMetrics.property_coverage * 100) : undefined}
								suffix="%"
								color="lvl4"
							/>
							<MetricCard
								label="Orphans"
								value={iteration.metrics.orphan_class_count}
								previousValue={previousMetrics?.orphan_class_count}
								color="warn"
								invertTrend
							/>
						</div>
					</div>
				{/if}

				<!-- Operations summary -->
				{#if iteration?.ops && iteration.ops.length > 0}
					<div class="bg-surface rounded-lg border border-edge p-4">
						<h3 class="text-sm font-semibold text-muted mb-3">Changes</h3>
						<div class="space-y-2 text-sm">
							{#if groupedOps.adds.length > 0}
								<div class="flex items-center gap-2">
									<span class="w-2 h-2 rounded-full bg-ok"></span>
									<span class="text-muted">{groupedOps.adds.length} added</span>
								</div>
								<div class="pl-4 space-y-1">
									{#each groupedOps.adds.slice(0, 5) as op}
										<div class="text-xs text-faint truncate" title={getOpDisplayName(op)}>
											{getOpDisplayName(op)}
										</div>
									{/each}
									{#if groupedOps.adds.length > 5}
										<div class="text-xs text-faint">+{groupedOps.adds.length - 5} more</div>
									{/if}
								</div>
							{/if}

							{#if groupedOps.updates.length > 0}
								<div class="flex items-center gap-2 mt-2">
									<span class="w-2 h-2 rounded-full bg-warn"></span>
									<span class="text-muted">{groupedOps.updates.length} updated</span>
								</div>
								<div class="pl-4 space-y-1">
									{#each groupedOps.updates.slice(0, 3) as op}
										<div class="text-xs text-faint truncate" title={getOpDisplayName(op)}>
											{getOpDisplayName(op)}
										</div>
									{/each}
									{#if groupedOps.updates.length > 3}
										<div class="text-xs text-faint">+{groupedOps.updates.length - 3} more</div>
									{/if}
								</div>
							{/if}

							{#if groupedOps.deletes.length > 0}
								<div class="flex items-center gap-2 mt-2">
									<span class="w-2 h-2 rounded-full bg-err"></span>
									<span class="text-muted">{groupedOps.deletes.length} deleted</span>
								</div>
								<div class="pl-4 space-y-1">
									{#each groupedOps.deletes.slice(0, 3) as op}
										<div class="text-xs text-faint truncate" title={getOpDisplayName(op)}>
											{getOpDisplayName(op)}
										</div>
									{/each}
									{#if groupedOps.deletes.length > 3}
										<div class="text-xs text-faint">+{groupedOps.deletes.length - 3} more</div>
									{/if}
								</div>
							{/if}

							{#if groupedOps.merges.length > 0}
								<div class="flex items-center gap-2 mt-2">
									<span class="w-2 h-2 rounded-full bg-info"></span>
									<span class="text-muted">{groupedOps.merges.length} merged</span>
								</div>
							{/if}
						</div>
					</div>
				{/if}

				<!-- Metrics charts (collapsible or smaller) -->
				<div class="hidden xl:block">
					<MetricsCharts {metrics} currentIteration={currentIdx} />
				</div>
			</div>
		</div>
	{/if}
</div>
