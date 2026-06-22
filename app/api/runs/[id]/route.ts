import { forwardToBridge } from "@/lib/bridge"

// GET /api/runs/{id} — Run lesen (v1.1; Cookie/Session werden durchgereicht).
export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  return forwardToBridge(request, `/runs/${encodeURIComponent(id)}`)
}
