import type { Crumb } from "$lib/components/layout/Breadcrumbs.svelte"
import type { PageLoad } from "./$types"

export const load: PageLoad = ({ params }) => {
  const breadcrumbs: Crumb[] = [
    { label: "runs", href: "/" },
    { label: params.name }
  ]
  return { breadcrumbs }
}
