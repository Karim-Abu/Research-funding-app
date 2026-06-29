import { forwardToBridge } from "@/lib/bridge"

// GET /api/projects/{id}/research-results — list public web research candidates (M9I-A).
export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  return forwardToBridge(
    request,
    `/projects/${encodeURIComponent(id)}/research-results`
  )
}
