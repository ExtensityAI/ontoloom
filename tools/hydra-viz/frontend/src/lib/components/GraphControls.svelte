<script lang="ts">
	import {
		ZoomInIcon,
		ZoomOutIcon,
		MaximizeIcon,
		TypeIcon,
		DownloadIcon,
		InfoIcon,
		SearchIcon
	} from '@lucide/svelte';
	import type { HydraSigma } from '$lib/graph/types';

	let {
		sigma,
		showLabels = true,
		showLegend,
		showSearch,
		onToggleLabels,
		onToggleLegend,
		onToggleSearch,
		onDownloadPng
	}: {
		sigma: HydraSigma | null;
		showLabels?: boolean;
		showLegend?: boolean;
		showSearch?: boolean;
		onToggleLabels?: () => void;
		onToggleLegend?: () => void;
		onToggleSearch?: () => void;
		onDownloadPng?: () => void;
	} = $props();

	const ZOOM_FACTOR = 1.5;
	const ANIMATION_DURATION = 200;

	const zoomIn = () => {
		if (!sigma) return;
		const camera = sigma.getCamera();
		camera.animate(
			{ ratio: camera.ratio / ZOOM_FACTOR },
			{ duration: ANIMATION_DURATION }
		);
	};

	const zoomOut = () => {
		if (!sigma) return;
		const camera = sigma.getCamera();
		camera.animate(
			{ ratio: camera.ratio * ZOOM_FACTOR },
			{ duration: ANIMATION_DURATION }
		);
	};

	const fitToScreen = () => {
		if (!sigma) return;
		sigma.getCamera().animatedReset({ duration: ANIMATION_DURATION });
	};
</script>

<div class="flex flex-col gap-1 border border-edge bg-surface p-1.5">
	<button
		type="button"
		onclick={zoomIn}
		class="p-1.5 hover:bg-hover transition-colors"
		title="Zoom in"
	>
		<ZoomInIcon class="w-4 h-4" />
	</button>

	<button
		type="button"
		onclick={zoomOut}
		class="p-1.5 hover:bg-hover transition-colors"
		title="Zoom out"
	>
		<ZoomOutIcon class="w-4 h-4" />
	</button>

	<button
		type="button"
		onclick={fitToScreen}
		class="p-1.5 hover:bg-hover transition-colors"
		title="Fit to screen"
	>
		<MaximizeIcon class="w-4 h-4" />
	</button>

	<div class="w-full h-px bg-edge my-1"></div>

	{#if onToggleLabels}
		<button
			type="button"
			onclick={onToggleLabels}
			class="p-1.5 hover:bg-hover transition-colors {showLabels ? 'text-accent' : 'text-muted'}"
			title="Toggle labels"
		>
			<TypeIcon class="w-4 h-4" />
		</button>
	{/if}

	{#if onToggleLegend}
		<button
			type="button"
			onclick={onToggleLegend}
			class="p-1.5 hover:bg-hover transition-colors {showLegend ? 'text-accent' : 'text-muted'}"
			title="Toggle legend"
		>
			<InfoIcon class="w-4 h-4" />
		</button>
	{/if}

	{#if onToggleSearch}
		<button
			type="button"
			onclick={onToggleSearch}
			class="p-1.5 hover:bg-hover transition-colors {showSearch ? 'text-accent' : 'text-muted'}"
			title="Search nodes"
		>
			<SearchIcon class="w-4 h-4" />
		</button>
	{/if}

	{#if onDownloadPng}
		<div class="w-full h-px bg-edge my-1"></div>
		<button
			type="button"
			onclick={onDownloadPng}
			class="p-1.5 hover:bg-hover transition-colors"
			title="Download as PNG"
		>
			<DownloadIcon class="w-4 h-4" />
		</button>
	{/if}
</div>
