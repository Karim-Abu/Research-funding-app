import { forwardToBridge } from "@/lib/bridge"

// GET /api/runs/{id}/phases — persistierter Phasenstand + technische
// Zusammenfassung (read-only; Cookie/Session werden durchgereicht).
export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  return forwardToBridge(request, `/runs/${encodeURIComponent(id)}/phases`)
}
