import { forwardToBridge } from "@/lib/bridge"

// PUT /api/projects/{id}/research-brief — public-safe Brief-Entwurf speichern.
// Fehlende Bridge-Route — Befund des Review-Truth-/Golden-Path-Pfads: die
// Browser-Aufrufe liefen ohne diese Datei ins Next-404 statt zur Bridge.
export async function PUT(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  return forwardToBridge(request, `/projects/${encodeURIComponent(id)}/research-brief`)
}
