import { forwardToBridge } from "@/lib/bridge"

// POST /api/projects/{id}/sources/text — Textquelle anlegen.
export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  return forwardToBridge(
    request,
    `/projects/${encodeURIComponent(id)}/sources/text`
  )
}
