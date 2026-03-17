import { fetchIteration } from '$lib/api/client'
import type { PageLoad } from './$types'

export const load: PageLoad = async ({ params, fetch }) => {
	const iteration = await fetchIteration(params.name, +params.iter, fetch)
	return { iteration }
}
