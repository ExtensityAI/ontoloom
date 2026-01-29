import { fetchIteration } from "$lib/api/client"
import { error } from "@sveltejs/kit"
import type { LayoutLoad } from "./$types"

export const load: LayoutLoad = async ({ params, fetch, parent }) => {
  const { name, iter } = params
  const iterNum = parseInt(iter, 10)

  // Get parent data (run and metrics)
  const parentData = await parent()

  // Validate iteration number
  if (isNaN(iterNum) || iterNum < 0 || iterNum >= parentData.run.iterations.length) {
    throw error(404, `Invalid iteration: ${iter}`)
  }

  // Load current iteration
  const iteration = await fetchIteration(name, iterNum, fetch)

  // Load previous iteration for diff comparison
  let previousIteration = null
  if (iterNum > 0) {
    previousIteration = await fetchIteration(name, iterNum - 1, fetch)
  }

  return {
    iteration,
    previousIteration,
    iterNum
  }
}
