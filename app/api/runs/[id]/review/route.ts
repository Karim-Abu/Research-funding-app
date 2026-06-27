import { forwardToBridge } from "@/lib/bridge"

// GET /api/runs/{id}/review — deterministic ReviewPackage (live, session-scoped).
export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  return forwardToBridge(request, `/runs/${encodeURIComponent(id)}/review`)
}
