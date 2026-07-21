import { forwardToBridge } from "@/lib/bridge"

export async function POST(
  request: Request,
  {
    params,
  }: {
    params: Promise<{ id: string; field: string; suggestion: string }>
  }
) {
  const { id, field, suggestion } = await params
  return forwardToBridge(
    request,
    `/runs/${encodeURIComponent(id)}/fields/${encodeURIComponent(field)}/suggestions/${encodeURIComponent(suggestion)}/accept`
  )
}
