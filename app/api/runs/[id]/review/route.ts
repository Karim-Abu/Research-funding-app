import { proxyToBridge } from "@/lib/bridge"

// POST /api/runs/{id}/review — Review-Entscheidungen + Feld-Edits (Re-Check).
export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  const body = await request.text()
  return proxyToBridge(`/runs/${encodeURIComponent(id)}/review`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body,
  })
}
