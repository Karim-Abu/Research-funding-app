import { forwardToBridge } from "@/lib/bridge"

// POST /api/projects/{id}/processing-confirmations — one-run cloud-processing
// confirmation (Milestone 9D.2). Returns 201 ProcessingConfirmation.
export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  return forwardToBridge(
    request,
    `/projects/${encodeURIComponent(id)}/processing-confirmations`
  )
}
