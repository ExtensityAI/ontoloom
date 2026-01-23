import { fetchRun, fetchIteration, fetchMetrics } from '$lib/api/client';
import { error } from '@sveltejs/kit';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ params, fetch }) => {
	const { name } = params;

	try {
		const [run, metrics] = await Promise.all([fetchRun(name, fetch), fetchMetrics(name, fetch)]);

		// Load first iteration if available
		let iteration = null;
		if (run.iterations.length > 0) {
			iteration = await fetchIteration(name, 0, fetch);
		}

		return {
			run,
			metrics,
			iteration
		};
	} catch (e) {
		const message = e instanceof Error ? e.message : 'Failed to load run';
		throw error(500, message);
	}
};
