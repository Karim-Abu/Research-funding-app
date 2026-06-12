import { proxyToBridge } from "@/lib/bridge"

// POST /api/runs/{id}/resume — setzt einen gestoppten Durchlauf fort.
export async function POST(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  return proxyToBridge(`/runs/${encodeURIComponent(id)}/resume`, {
    method: "POST",
  })
}
