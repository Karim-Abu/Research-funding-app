import { forwardToBridge } from "@/lib/bridge"

// POST /api/projects/{id}/search-query-firewall/preview — screen a web-research query
// through the Search Query Firewall (M9J). Returns a sanitized query + decision.
export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  return forwardToBridge(
    request,
    `/projects/${encodeURIComponent(id)}/search-query-firewall/preview`
  )
}
