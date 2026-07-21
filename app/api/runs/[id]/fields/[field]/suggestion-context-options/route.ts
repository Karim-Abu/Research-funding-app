import { forwardToBridge } from "@/lib/bridge"

export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string; field: string }> }
) {
  const { id, field } = await params
  return forwardToBridge(
    request,
    `/runs/${encodeURIComponent(id)}/fields/${encodeURIComponent(field)}/suggestion-context-options`
  )
}
