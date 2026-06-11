import { proxyToBridge } from "@/lib/bridge"

// POST /api/runs — startet einen Analyse-Durchlauf an der Bridge.
export async function POST(request: Request) {
  const body = await request.text()
  return proxyToBridge("/runs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body,
  })
}
