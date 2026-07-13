import { forwardToBridge } from "@/lib/bridge"

// POST /api/research-results/{id}/discard — Ergebnis-Kandidat persistent verwerfen (R8).
export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  return forwardToBridge(
    request,
    `/research-results/${encodeURIComponent(id)}/discard`
  )
}
