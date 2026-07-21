import { forwardToBridge } from "@/lib/bridge"

export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  return forwardToBridge(
    request,
    `/research-results/${encodeURIComponent(id)}/partner-eligibility-review`
  )
}
