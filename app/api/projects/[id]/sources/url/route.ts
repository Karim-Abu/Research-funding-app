import { forwardToBridge } from "@/lib/bridge"

// POST /api/projects/{id}/sources/url — URL-Import (in dieser Beta deaktiviert,
// die Bridge antwortet mit 503).
export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  return forwardToBridge(
    request,
    `/projects/${encodeURIComponent(id)}/sources/url`
  )
}
