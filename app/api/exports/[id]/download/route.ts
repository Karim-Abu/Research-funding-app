import { forwardToBridge } from "@/lib/bridge"

// GET /api/exports/{id}/download — binary export download (octet-stream).
// forwardToBridge streams the body and preserves Content-Disposition.
export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  return forwardToBridge(request, `/exports/${encodeURIComponent(id)}/download`)
}
