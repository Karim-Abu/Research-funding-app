import { forwardToBridge } from "@/lib/bridge"

export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  return forwardToBridge(request, `/runs/${encodeURIComponent(id)}/transfer-copy-events`)
}
