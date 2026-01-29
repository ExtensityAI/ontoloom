<script lang="ts">
	import { TrendingUpIcon, TrendingDownIcon, MinusIcon } from '@lucide/svelte';

	let {
		label,
		value,
		previousValue,
		suffix = '',
		color = 'accent',
		invertTrend = false
	}: {
		label: string;
		value: number;
		previousValue?: number;
		suffix?: string;
		color?: string;
		invertTrend?: boolean;
	} = $props();

	// Calculate trend
	const trend = $derived.by(() => {
		if (previousValue === undefined) return 'neutral';
		if (value > previousValue) return 'up';
		if (value < previousValue) return 'down';
		return 'neutral';
	});

	const diff = $derived(previousValue !== undefined ? value - previousValue : 0);

	// Determine if trend is good or bad
	const isPositive = $derived.by(() => {
		if (trend === 'neutral') return null;
		// For metrics where decrease is good (like orphans), invert
		if (invertTrend) return trend === 'down';
		return trend === 'up';
	});

	// Get color class based on color prop
	const colorClass = $derived(`text-${color}`);
</script>

<div class="flex items-center justify-between">
	<div class="text-sm text-faint">{label}</div>
	<div class="flex items-center gap-2">
		<div class="text-lg font-semibold {colorClass}">
			{value}{suffix}
		</div>
		{#if previousValue !== undefined && trend !== 'neutral'}
			<div
				class="flex items-center text-sm {isPositive ? 'text-ok' : isPositive === false ? 'text-err' : 'text-muted'}"
			>
				{#if trend === 'up'}
					<TrendingUpIcon class="w-3 h-3" />
				{:else if trend === 'down'}
					<TrendingDownIcon class="w-3 h-3" />
				{:else}
					<MinusIcon class="w-3 h-3" />
				{/if}
				<span class="ml-0.5">{diff > 0 ? '+' : ''}{diff}</span>
			</div>
		{/if}
	</div>
</div>
