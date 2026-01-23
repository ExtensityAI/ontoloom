<script lang="ts">
	import '../layout.css';
	import favicon from '$lib/assets/favicon.svg';
	import ExtensityLogo from '$lib/components/ExtensityLogo.svelte';

	let { children } = $props();
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
	<title>ontology-hydra Visualizer</title>
</svelte:head>

<div class="min-h-screen">
	<header class="border-b border-neutral-900 bg-neutral-950 backdrop-blur-sm sticky top-0 z-50">
		<div class="max-w-7xl mx-auto py-4 flex items-center gap-4">
			<a href="/" class="text-xl text-lime-500 font-medium hover:opacity-80 transition-opacity">
				ontology-hydra <span class="text-neutral-500">\</span> <span class="text-lime-500">Visualizer</span>
			</a>
			
			<div class='flex-1'></div>
			<a href='https://extensity.ai'><ExtensityLogo class='h-6'/></a>
		</div>
	</header>

	<main class="max-w-7xl mx-auto py-8">
		{@render children()}
	</main>
</div>
