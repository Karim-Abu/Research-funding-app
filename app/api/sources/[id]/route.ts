import { forwardToBridge } from "@/lib/bridge"

// GET /api/sources/{id} — Quelle lesen (Status-Polling); DELETE — Quelle löschen.
export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  return forwardToBridge(request, `/sources/${encodeURIComponent(id)}`)
}

export async function DELETE(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  return forwardToBridge(request, `/sources/${encodeURIComponent(id)}`)
}
