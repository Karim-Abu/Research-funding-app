import { forwardToBridge } from "@/lib/bridge"

// POST /api/projects/{id}/market-comparisons — start a market/competitor comparison (M9I-B).
export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  return forwardToBridge(
    request,
    `/projects/${encodeURIComponent(id)}/market-comparisons`
  )
}
