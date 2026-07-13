import { forwardToBridge } from "@/lib/bridge"

// GET /api/projects/{id}/budget/precheck — read-only Budget-Vorprüfung
// (run-unabhängig, Rechnung ausschliesslich im Backend-Rule-Kern).
export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  return forwardToBridge(
    request,
    `/projects/${encodeURIComponent(id)}/budget/precheck`
  )
}
