import { forwardToBridge } from "@/lib/bridge"

// POST /api/runs/{id}/human-decisions — typed review decision / section comment.
export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  return forwardToBridge(request, `/runs/${encodeURIComponent(id)}/human-decisions`)
}
