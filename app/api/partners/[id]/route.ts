import { forwardToBridge } from "@/lib/bridge"

// PATCH /api/partners/{id} — Partner aktualisieren; DELETE — Partner löschen (204).
export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  return forwardToBridge(request, `/partners/${encodeURIComponent(id)}`)
}

export async function DELETE(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  return forwardToBridge(request, `/partners/${encodeURIComponent(id)}`)
}
