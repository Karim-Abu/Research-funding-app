import { forwardToBridge } from "@/lib/bridge"

// GET /api/runs/{id}/fields/{field}/versions/{version} — RUN 4B: Volltext
// einer unveränderlichen Altversion (bestehender Backend-Endpunkt; genutzt
// für die client-orchestrierte Wiederherstellung).
export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string; field: string; version: string }> }
) {
  const { id, field, version } = await params
  return forwardToBridge(
    request,
    `/runs/${encodeURIComponent(id)}/fields/${encodeURIComponent(field)}/versions/${encodeURIComponent(version)}`
  )
}
