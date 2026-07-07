import { forwardToBridge } from "@/lib/bridge"

// GET /api/runs/{id}/review/fix-queue — gruppierte Findings + Fix Queue (R2.4).
export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  return forwardToBridge(request, `/runs/${encodeURIComponent(id)}/review/fix-queue`)
}
