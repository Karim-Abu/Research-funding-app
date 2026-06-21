import { forwardToBridge } from "@/lib/bridge"

// GET /api/projects/{id} — Projekt lesen; PATCH — Projekt aktualisieren.
export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  return forwardToBridge(request, `/projects/${encodeURIComponent(id)}`)
}

export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  return forwardToBridge(request, `/projects/${encodeURIComponent(id)}`)
}
