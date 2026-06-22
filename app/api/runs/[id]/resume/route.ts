import { forwardToBridge } from "@/lib/bridge"

// POST /api/runs/{id}/resume — Finalisierung nach Freigabe (v1.1).
export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  return forwardToBridge(request, `/runs/${encodeURIComponent(id)}/resume`)
}
