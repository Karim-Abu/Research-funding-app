import { forwardToBridge } from "@/lib/bridge"

// GET /api/exports/{id} — ExportArtifact status (live, session-scoped).
export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  return forwardToBridge(request, `/exports/${encodeURIComponent(id)}`)
}
