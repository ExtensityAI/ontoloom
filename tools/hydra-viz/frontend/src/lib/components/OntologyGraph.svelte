<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { Sigma } from 'sigma';
	import { createOntologyGraph } from '$lib/graph/parser';
	import { createNodeReducer, createEdgeReducer } from '$lib/visualizer/reducers';
	import { createSelection, type NodeSelection } from '$lib/visualizer/selection';
	import type { Ontology } from '$lib/api/types';
	import type { HydraGraph, HydraSigma } from '$lib/graph/types';
	import type { OntologyDiff } from '$lib/utils/diff';
	import NodeSearch from '$lib/ui/NodeSearch.svelte';
	import GraphLegend from '$lib/components/GraphLegend.svelte';
	import GraphControls from '$lib/components/GraphControls.svelte';
	import { SearchIcon, XIcon, InfoIcon } from '@lucide/svelte';

	// Camera animation settings
	const CAMERA_ANIMATION_MS = 300;
	const CAMERA_ZOOM_RATIO = 0.5;

	let { ontology, diff }: { ontology: Ontology | null; diff?: OntologyDiff } = $props();

	let container: HTMLDivElement;
	let sigma: HydraSigma | null = $state(null);
	let graph: HydraGraph | null = $state(null);
	let activeSelection: NodeSelection | null = $state(null);
	let showSearch = $state(false);
	let showLegend = $state(true);
	let showLabels = $state(true);

	// Compute max level from graph
	let maxLevel = $derived.by(() => {
		if (!graph) return 5;
		let max = 0;
		graph.forEachNode((_, attrs) => {
			if (attrs.level > max) max = attrs.level;
		});
		return max;
	});

	const getActiveSelection = () => activeSelection;
	const getDiff = () => diff;

	const handleNodeClick = (nodeId: string) => {
		if (!graph) return;
		activeSelection = createSelection(nodeId, graph);
		sigma?.refresh();
	};

	const handleSearchSelect = (nodeId: string) => {
		if (!graph || !sigma) return;
		activeSelection = createSelection(nodeId, graph);

		// Center camera on selected node
		const nodePos = sigma.getNodeDisplayData(nodeId);
		if (nodePos) {
			sigma.getCamera().animate(
				{ x: nodePos.x, y: nodePos.y, ratio: CAMERA_ZOOM_RATIO },
				{ duration: CAMERA_ANIMATION_MS }
			);
		}

		sigma.refresh();
		showSearch = false;
	};

	const clearSelection = () => {
		activeSelection = null;
		sigma?.refresh();
	};

	const toggleLabels = () => {
		showLabels = !showLabels;
		if (sigma) {
			sigma.setSetting('renderLabels', showLabels);
		}
	};

	const downloadPng = async () => {
		if (!sigma || !container) return;

		// Get the canvas layers
		const layers = container.querySelectorAll('canvas');
		if (layers.length === 0) return;

		// Create a temporary canvas to merge all layers
		const canvas = document.createElement('canvas');
		const mainCanvas = layers[0] as HTMLCanvasElement;
		canvas.width = mainCanvas.width;
		canvas.height = mainCanvas.height;

		const ctx = canvas.getContext('2d');
		if (!ctx) return;

		// Fill with background color
		ctx.fillStyle = '#0c0a09'; // bg color
		ctx.fillRect(0, 0, canvas.width, canvas.height);

		// Draw all canvas layers
		layers.forEach((layer) => {
			ctx.drawImage(layer as HTMLCanvasElement, 0, 0);
		});

		// Download
		const link = document.createElement('a');
		link.download = 'ontology-graph.png';
		link.href = canvas.toDataURL('image/png');
		link.click();
	};

	const initGraph = () => {
		if (!ontology || !container) return;

		// Cleanup previous
		cleanup();

		// Create graph from ontology (positions are computed in parser)
		graph = createOntologyGraph(ontology);

		// Create Sigma instance
		sigma = new Sigma(graph, container, {
			nodeReducer: createNodeReducer(getActiveSelection, getDiff),
			edgeReducer: createEdgeReducer(getActiveSelection, getDiff),
			allowInvalidContainer: true,
			renderLabels: showLabels,
			labelFont: 'system-ui, sans-serif',
			labelSize: 12,
			labelColor: { color: '#e2e8f0' },
			defaultEdgeType: 'arrow'
		});

		// Handle clicks
		sigma.on('clickNode', ({ node }) => handleNodeClick(node));
		sigma.on('clickStage', () => clearSelection());

		// Fit camera to show all nodes with padding
		const camera = sigma.getCamera();
		camera.animatedReset({ duration: CAMERA_ANIMATION_MS });
	};

	const cleanup = () => {
		sigma?.kill();
		sigma = null;
		graph = null;
		activeSelection = null;
	};

	// Keyboard shortcuts
	const handleKeydown = (event: KeyboardEvent) => {
		// Don't trigger if typing in an input
		if (event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement) {
			return;
		}

		switch (event.key) {
			case 'l':
			case 'L':
				showLegend = !showLegend;
				break;
			case 'f':
			case 'F':
				if (!event.ctrlKey && !event.metaKey) {
					showSearch = !showSearch;
					event.preventDefault();
				}
				break;
			case 'Escape':
				if (showSearch) {
					showSearch = false;
				} else if (activeSelection) {
					clearSelection();
				}
				break;
		}
	};

	onMount(() => {
		initGraph();
		window.addEventListener('keydown', handleKeydown);
	});

	onDestroy(() => {
		cleanup();
		window.removeEventListener('keydown', handleKeydown);
	});

	// Re-initialize when ontology changes
	$effect(() => {
		if (ontology && container) {
			initGraph();
		}
	});

	// Refresh when diff changes
	$effect(() => {
		if (diff !== undefined && sigma) {
			sigma.refresh();
		}
	});
</script>

<div class="relative w-full h-full bg-bg rounded-lg overflow-hidden border border-edge">
	<div bind:this={container} class="w-full h-full"></div>

	<!-- Graph controls (left side) -->
	{#if ontology}
		<div class="absolute top-3 left-3 z-10">
			<GraphControls
				{sigma}
				{showLabels}
				onToggleLabels={toggleLabels}
				onDownloadPng={downloadPng}
			/>
		</div>
	{/if}

	<!-- Top-right controls -->
	<div class="absolute top-3 right-3 flex gap-2">
		<button
			type="button"
			onclick={() => (showLegend = !showLegend)}
			class="p-2 bg-surface/80 backdrop-blur-sm rounded-lg border border-edge hover:bg-hover/80 transition-colors {showLegend ? 'text-accent' : ''}"
			title="Toggle legend (L)"
		>
			<InfoIcon class="w-5 h-5" />
		</button>
		<button
			type="button"
			onclick={() => (showSearch = !showSearch)}
			class="p-2 bg-surface/80 backdrop-blur-sm rounded-lg border border-edge hover:bg-hover/80 transition-colors {showSearch ? 'text-accent' : ''}"
			title="Search nodes (F)"
		>
			<SearchIcon class="w-5 h-5" />
		</button>
	</div>

	<!-- Legend -->
	{#if showLegend && ontology}
		<div class="absolute bottom-3 right-3 z-10">
			<GraphLegend {maxLevel} {diff} />
		</div>
	{/if}

	<!-- Search overlay -->
	{#if showSearch && graph}
		<div class="absolute top-16 right-3 z-10">
			<div class="relative">
				<NodeSearch {graph} onSelect={handleSearchSelect} />
				<button
					type="button"
					onclick={() => (showSearch = false)}
					class="absolute -top-2 -right-2 p-1 bg-hover rounded-full hover:bg-faint/30"
				>
					<XIcon class="w-4 h-4" />
				</button>
			</div>
		</div>
	{/if}

	<!-- Selection info -->
	{#if activeSelection}
		<div
			class="absolute bottom-3 left-3 max-w-sm rounded-lg border border-edge bg-surface p-3 {showLegend ? 'right-48' : 'right-3'}"
		>
			<div class="flex items-start justify-between gap-4">
				<div>
					<div class="font-semibold text-accent">{activeSelection.node}</div>
					<div class="text-sm text-muted mt-1">
						Level {activeSelection.attrs.level} ·
						{activeSelection.parents.size} ancestors ·
						{activeSelection.children.size} children
					</div>
				</div>
				<button
					type="button"
					onclick={clearSelection}
					class="p-1 hover:bg-hover rounded transition-colors shrink-0"
					title="Clear selection (Escape)"
				>
					<XIcon class="w-4 h-4" />
				</button>
			</div>
		</div>
	{/if}

	<!-- Empty state -->
	{#if !ontology}
		<div class="absolute inset-0 flex items-center justify-center bg-bg/80 text-faint">
			No ontology data available
		</div>
	{/if}

	<!-- Keyboard shortcuts hint -->
	{#if ontology && !showSearch && !activeSelection}
		<div class="absolute bottom-3 left-3 text-sm text-faint/50">
			Press <kbd class="px-1 py-0.5 bg-surface rounded text-faint">F</kbd> to search ·
			<kbd class="px-1 py-0.5 bg-surface rounded text-faint">L</kbd> legend
		</div>
	{/if}
</div>
