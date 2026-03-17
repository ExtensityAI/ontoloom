import { error } from "@sveltejs/kit"
import type { LayoutLoad } from "./$types"

export const load: LayoutLoad = async ({ params }) => {
  const iterNum = parseInt(params.iter, 10)

  if (isNaN(iterNum) || iterNum < 0) {
    throw error(404, `Invalid iteration: ${params.iter}`)
  }

  return { iterNum }
}
