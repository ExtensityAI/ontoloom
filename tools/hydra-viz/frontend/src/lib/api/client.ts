import type { RunSummary, RunDetail, IterationDetail } from './types';

type Fetch = typeof fetch;

const API_BASE = '/api';

async function fetchJson<T>(url: string, customFetch: Fetch = fetch): Promise<T> {
	const response = await customFetch(url);
	if (!response.ok) {
		throw new Error(`API error: ${response.status} ${response.statusText}`);
	}
	return response.json();
}

export async function fetchRuns(customFetch?: Fetch): Promise<RunSummary[]> {
	return fetchJson<RunSummary[]>(`${API_BASE}/runs`, customFetch);
}

export async function fetchRun(name: string, customFetch?: Fetch): Promise<RunDetail> {
	return fetchJson<RunDetail>(`${API_BASE}/runs/${encodeURIComponent(name)}`, customFetch);
}

export async function fetchIteration(
	name: string,
	idx: number,
	customFetch?: Fetch
): Promise<IterationDetail> {
	return fetchJson<IterationDetail>(
		`${API_BASE}/runs/${encodeURIComponent(name)}/iterations/${idx}`,
		customFetch
	);
}
