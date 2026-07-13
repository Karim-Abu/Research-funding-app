import { forwardToBridge } from "@/lib/bridge"

// GET /api/runs/{id}/review/status — kanonischer Status-View (R1.2/R1.3).
export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  return forwardToBridge(request, `/runs/${encodeURIComponent(id)}/review/status`)
}
