import { fetchMetrics, fetchRun } from "$lib/api/client"
import type { LayoutLoad } from "./$types"

export const load: LayoutLoad = async ({ params, fetch }) => {
  const { name } = params

  const [run, metrics] = await Promise.all([fetchRun(name, fetch), fetchMetrics(name, fetch)])

  return {
    run,
    metrics
  }
}
