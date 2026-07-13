import { forwardToBridge } from "@/lib/bridge"

// POST /api/projects/{id}/market-research/queries/preview — bearbeitete Markt-Query
// erneut prüfen: Firewall + neue pending Freigabe (R8).
export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  return forwardToBridge(
    request,
    `/projects/${encodeURIComponent(id)}/market-research/queries/preview`
  )
}
