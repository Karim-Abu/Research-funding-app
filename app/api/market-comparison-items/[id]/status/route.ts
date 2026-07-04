import { forwardToBridge } from "@/lib/bridge"

// POST /api/market-comparison-items/{id}/status — accept/reject/needs-review (M9I-B).
export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  return forwardToBridge(
    request,
    `/market-comparison-items/${encodeURIComponent(id)}/status`
  )
}
