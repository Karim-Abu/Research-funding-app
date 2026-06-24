import { forwardToBridge } from "@/lib/bridge"

// POST createEvidenceLink — verknüpft einen Anchor mit der aktuellen Entwurfsversion.
export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string; field: string }> }
) {
  const { id, field } = await params
  return forwardToBridge(
    request,
    `/runs/${encodeURIComponent(id)}/fields/${encodeURIComponent(field)}/evidence-links`
  )
}
