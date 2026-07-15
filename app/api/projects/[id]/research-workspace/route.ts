import { forwardToBridge } from "@/lib/bridge"

// GET /api/projects/{id}/research-workspace — Brief + Query-Historie der öffentlichen Recherche.
// Fehlende Bridge-Route — Befund des Review-Truth-/Golden-Path-Pfads: die
// Browser-Aufrufe liefen ohne diese Datei ins Next-404 statt zur Bridge.
export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  return forwardToBridge(request, `/projects/${encodeURIComponent(id)}/research-workspace`)
}
