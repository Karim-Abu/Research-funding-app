import { forwardToBridge } from "@/lib/bridge"

// POST /api/projects/{id}/market-research/run — execute the confirmed market-research
// topic via the existing research vertical (RESEARCH.1b, synchronous).
export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  return forwardToBridge(
    request,
    `/projects/${encodeURIComponent(id)}/market-research/run`
  )
}
