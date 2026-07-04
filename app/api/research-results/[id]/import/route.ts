import { forwardToBridge } from "@/lib/bridge"

// POST /api/research-results/{id}/import — import a result as a normal source (M9I-A).
export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  return forwardToBridge(
    request,
    `/research-results/${encodeURIComponent(id)}/import`
  )
}
