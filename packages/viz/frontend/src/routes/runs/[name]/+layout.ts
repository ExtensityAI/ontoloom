import { fetchRun } from "$lib/api/client"
import type { LayoutLoad } from "./$types"

export const load: LayoutLoad = async ({ params, fetch }) => {
  const run = await fetchRun(params.name, fetch)
  return { run }
}
