<script lang="ts">
	import favicon from '$lib/assets/favicon.svg';
	import ExtensityLogo from '$lib/components/ExtensityLogo.svelte';
	import '../layout.css';

	let { children } = $props();
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
	<title>ontology-hydra Visualizer</title>
</svelte:head>

<div class="min-h-screen">
	<header class="border-b border-neutral-900 bg-neutral-950">
		<div class="max-w-7xl px-8 mx-auto py-4 flex items-center gap-4">
			<a href="/" class="text-xl text-emerald-500 font-medium hover:opacity-80 transition-opacity">
				ontology-hydra <span class="text-neutral-500">\</span> <span class="text-emerald-500">Visualizer</span>
			</a>
			
			<div class='flex-1'></div>
			<a href='https://extensity.ai'><ExtensityLogo class='h-6'/></a>
		</div>
	</header>

	<main class="max-w-7xl px-8 mx-auto py-8">
		{@render children()}
	</main>
</div>
