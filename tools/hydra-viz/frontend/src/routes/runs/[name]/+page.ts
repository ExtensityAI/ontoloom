import { getRunCrumbs } from '$lib/utils/navigation'
import type { PageLoad } from './$types'

export const load: PageLoad = ({ params }) => {
	return { breadcrumbs: getRunCrumbs(params.name) }
}
