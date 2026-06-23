import { forwardToBridge } from "@/lib/bridge"

// GET /api/runs/{id}/evidence — EvidenceAnchors des Runs (deterministische Belege).
export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  return forwardToBridge(request, `/runs/${encodeURIComponent(id)}/evidence`)
}
