import { forwardToBridge } from "@/lib/bridge"

// GET /api/projects/{id}/imports — Import-Kandidaten auflisten;
// POST — verarbeitete Quelle auf Portal-Felder mappen (R3.2).
export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  return forwardToBridge(request, `/projects/${encodeURIComponent(id)}/imports`)
}

export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  return forwardToBridge(request, `/projects/${encodeURIComponent(id)}/imports`)
}
