import { forwardToBridge } from "@/lib/bridge"

// POST /api/runs/{id}/rechecks — start a deterministic targeted recheck (202).
export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  return forwardToBridge(request, `/runs/${encodeURIComponent(id)}/rechecks`)
}
