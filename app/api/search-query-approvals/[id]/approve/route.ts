import { forwardToBridge } from "@/lib/bridge"

// POST /api/search-query-approvals/{id}/approve — approve a firewall-sanitized query (M9J).
export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  return forwardToBridge(
    request,
    `/search-query-approvals/${encodeURIComponent(id)}/approve`
  )
}
