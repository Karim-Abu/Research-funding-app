import { forwardToBridge } from "@/lib/bridge"

// POST /api/research-briefs/{id}/run — freigegebene Brief-Recherche ausführen.
// Fehlende Bridge-Route — Befund des Review-Truth-/Golden-Path-Pfads: die
// Browser-Aufrufe liefen ohne diese Datei ins Next-404 statt zur Bridge.
export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  return forwardToBridge(request, `/research-briefs/${encodeURIComponent(id)}/run`)
}
