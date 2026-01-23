import { fetchRuns } from '$lib/api/client';
import { error } from '@sveltejs/kit';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch }) => {
	try {
		const runs = await fetchRuns(fetch);
		return { runs };
	} catch (e) {
		const message = e instanceof Error ? e.message : 'Failed to load runs';
		throw error(500, message);
	}
};
