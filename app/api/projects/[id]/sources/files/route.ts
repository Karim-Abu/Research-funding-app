import { forwardToBridge } from "@/lib/bridge"

// POST /api/projects/{id}/sources/files — Datei-Upload (multipart).
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
