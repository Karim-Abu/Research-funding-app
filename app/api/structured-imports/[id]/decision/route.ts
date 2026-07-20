import { forwardToBridge } from "@/lib/bridge"

export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  return forwardToBridge(
    request,
    `/structured-imports/${encodeURIComponent(id)}/decision`
  )
}

export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  return forwardToBridge(
    request,
    `/structured-imports/${encodeURIComponent(id)}/decision`
  )
}
