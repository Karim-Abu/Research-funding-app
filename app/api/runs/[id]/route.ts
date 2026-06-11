import { proxyToBridge } from "@/lib/bridge"

// GET /api/runs/{id} — Status eines Durchlaufs (Polling).
export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  return proxyToBridge(`/runs/${encodeURIComponent(id)}`)
}
