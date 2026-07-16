import { forwardToBridge } from "@/lib/bridge"

// GET /api/runs/{id}/review/check-status — autoritativer Check-Status je
// Prüfbereich (Teil A). Ohne diese Bridge-Route lief useCheckStatus im
// Browser ins Leere und die Screens fielen still auf pkg.blocker_count
// zurück (Befund des Review-Truth-Pfads).
export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  return forwardToBridge(
    request,
    `/runs/${encodeURIComponent(id)}/review/check-status`
  )
}
