import { forwardToBridge } from "@/lib/bridge"

// POST /api/runs/{id}/approvals — role-gated review approval (scope run|field).
export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  return forwardToBridge(request, `/runs/${encodeURIComponent(id)}/approvals`)
}
