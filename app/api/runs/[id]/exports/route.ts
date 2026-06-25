import { forwardToBridge } from "@/lib/bridge"

// POST /api/runs/{id}/exports — create a deterministic export (202 AsyncAccepted).
export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  return forwardToBridge(request, `/runs/${encodeURIComponent(id)}/exports`)
}
