import { forwardToBridge } from "@/lib/bridge"

// POST /api/projects/{id}/market-research/plan — topic suggestion + query preview
// (RESEARCH.1b, no DB writes, no provider call).
export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  return forwardToBridge(
    request,
    `/projects/${encodeURIComponent(id)}/market-research/plan`
  )
}
