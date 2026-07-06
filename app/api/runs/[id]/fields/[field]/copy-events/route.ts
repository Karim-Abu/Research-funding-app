import { forwardToBridge } from "@/lib/bridge"

// createCopyEvent (Slice 3, Council E2-A): record one Innolink copy action —
// metadata only, never the field text. Copying itself is never blocked; the
// UI stays fail-open when this call fails.
export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string; field: string }> }
) {
  const { id, field } = await params
  return forwardToBridge(
    request,
    `/runs/${encodeURIComponent(id)}/fields/${encodeURIComponent(field)}/copy-events`
  )
}
