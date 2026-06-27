import { forwardToBridge } from "@/lib/bridge"

// GET /api/operations/{id} — AsyncOperation-Polling (v1.1).
export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  return forwardToBridge(request, `/operations/${encodeURIComponent(id)}`)
}
