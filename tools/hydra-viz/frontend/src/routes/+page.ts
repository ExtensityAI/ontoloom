import { fetchRuns } from '$lib/api/client'
import type { PageLoad } from './$types'

export const load: PageLoad = async ({ fetch }) => {
	return { runs: await fetchRuns(fetch) }
}
