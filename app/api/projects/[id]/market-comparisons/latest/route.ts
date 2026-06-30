import { forwardToBridge } from "@/lib/bridge"

// GET /api/projects/{id}/market-comparisons/latest — latest comparison + items (M9I-B).
export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  return forwardToBridge(
    request,
    `/projects/${encodeURIComponent(id)}/market-comparisons/latest`
  )
}
