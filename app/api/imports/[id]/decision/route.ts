import { forwardToBridge } from "@/lib/bridge"

// POST /api/imports/{id}/decision — menschliche Entscheidung je Kandidat
// (Übernehmen / Als Quelle speichern / Ignorieren), R3.2.
export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  return forwardToBridge(request, `/imports/${encodeURIComponent(id)}/decision`)
}

export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  return forwardToBridge(request, `/imports/${encodeURIComponent(id)}/decision`)
}
