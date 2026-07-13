import { forwardToBridge } from "@/lib/bridge"

// GET /api/runs/{id}/fields/{field}/suggestion — offene A2-Suggestion zur
// aktuellen Basisversion (read-only; z. B. aus dem Analyse-Lauf).
export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string; field: string }> }
) {
  const { id, field } = await params
  return forwardToBridge(
    request,
    `/runs/${encodeURIComponent(id)}/fields/${encodeURIComponent(field)}/suggestion`
  )
}
