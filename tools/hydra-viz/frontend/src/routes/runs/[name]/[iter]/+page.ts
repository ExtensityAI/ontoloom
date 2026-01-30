import { getIterationCrumbs } from '$lib/utils/navigation'
import type { PageLoad } from './$types'

export const load: PageLoad = ({ params }) => {
	return { breadcrumbs: getIterationCrumbs(params.name, params.iter) }
}
