import type { Crumb } from "$lib/components/layout/Breadcrumbs.svelte"
import type { PageLoad } from "./$types"

export const load: PageLoad = ({ params }) => {
  const basePath = `/runs/${encodeURIComponent(params.name)}`
  const breadcrumbs: Crumb[] = [
    { label: "runs", href: "/" },
    { label: params.name, href: basePath },
    { label: params.iter }
  ]
  return { breadcrumbs }
}
