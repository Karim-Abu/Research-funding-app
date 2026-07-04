import { forwardToBridge } from "@/lib/bridge"

// GET /api/research-tasks/{id} — read a public web research task (M9I-A).
export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  return forwardToBridge(request, `/research-tasks/${encodeURIComponent(id)}`)
}
