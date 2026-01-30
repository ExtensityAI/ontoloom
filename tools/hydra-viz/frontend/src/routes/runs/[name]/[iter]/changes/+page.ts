import { getIterationSubpageCrumbs } from '$lib/utils/navigation'
import type { PageLoad } from './$types'

export const load: PageLoad = ({ params }) => {
	return { breadcrumbs: getIterationSubpageCrumbs(params.name, params.iter, 'changes') }
}
