import { forwardToBridge } from "@/lib/bridge"

// GET /api/runs/{id}/fields/{field}/versions — RUN 4B: Metadaten-Historie
// aller Versionen eines Portalfeldes, neueste zuerst (ohne Volltexte).
export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string; field: string }> }
) {
  const { id, field } = await params
  return forwardToBridge(
    request,
    `/runs/${encodeURIComponent(id)}/fields/${encodeURIComponent(field)}/versions`
  )
}
