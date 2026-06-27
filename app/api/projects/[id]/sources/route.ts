import { forwardToBridge } from "@/lib/bridge"

// GET /api/projects/{id}/sources — Quellenliste; POST — Datei-Upload (multipart).
export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  return forwardToBridge(request, `/projects/${encodeURIComponent(id)}/sources`)
}

export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  return forwardToBridge(
    request,
    `/projects/${encodeURIComponent(id)}/sources/files`
  )
}
