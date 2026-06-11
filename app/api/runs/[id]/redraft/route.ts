import { proxyToBridge } from "@/lib/bridge"

// POST /api/runs/{id}/redraft — KI-Neuentwurf für ein Feld.
export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  const body = await request.text()
  return proxyToBridge(`/runs/${encodeURIComponent(id)}/redraft`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body,
  })
}
