import { forwardToBridge } from "@/lib/bridge"

// GET /api/runs/{id}/portal-fields — read-only Registry-Feldkatalog (Slice 4).
export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  return forwardToBridge(request, `/runs/${encodeURIComponent(id)}/portal-fields`)
}
