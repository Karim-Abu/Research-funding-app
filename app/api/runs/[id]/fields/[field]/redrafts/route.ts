import { forwardToBridge } from "@/lib/bridge"

// createRedraft (Milestone 9D): request an advisory A2 draft suggestion for the
// Solution & Innovation field. Async (202); the suggestion is read via the operation.
export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string; field: string }> }
) {
  const { id, field } = await params
  return forwardToBridge(
    request,
    `/runs/${encodeURIComponent(id)}/fields/${encodeURIComponent(field)}/redrafts`
  )
}
