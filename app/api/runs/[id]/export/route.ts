import { proxyToBridge } from "@/lib/bridge"

// GET /api/runs/{id}/export?kind=word|markdown|json_audit — Binary-Download.
// proxyToBridge streamt den Body und reicht Content-Disposition durch.
export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  const kind = new URL(request.url).searchParams.get("kind") ?? "word"
  return proxyToBridge(
    `/runs/${encodeURIComponent(id)}/export?kind=${encodeURIComponent(kind)}`
  )
}
