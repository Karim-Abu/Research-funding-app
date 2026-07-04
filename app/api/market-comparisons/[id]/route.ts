import { forwardToBridge } from "@/lib/bridge"

// GET /api/market-comparisons/{id} — read a market comparison + items (M9I-B).
export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  return forwardToBridge(request, `/market-comparisons/${encodeURIComponent(id)}`)
}
