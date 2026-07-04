import { forwardToBridge } from "@/lib/bridge"

// POST /api/projects/{id}/research-tasks — start a public web research task (M9I-A).
export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  return forwardToBridge(
    request,
    `/projects/${encodeURIComponent(id)}/research-tasks`
  )
}
