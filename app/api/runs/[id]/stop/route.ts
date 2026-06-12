import { proxyToBridge } from "@/lib/bridge"

// POST /api/runs/{id}/stop — stoppt einen laufenden Durchlauf.
export async function POST(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  return proxyToBridge(`/runs/${encodeURIComponent(id)}/stop`, {
    method: "POST",
  })
}
