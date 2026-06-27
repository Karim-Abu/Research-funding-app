import { forwardToBridge } from "@/lib/bridge"

// DELETE deleteEvidenceLink — markiert die Verknüpfung als entfernt (204).
export async function DELETE(
  request: Request,
  { params }: { params: Promise<{ id: string; field: string; link: string }> }
) {
  const { id, field, link } = await params
  return forwardToBridge(
    request,
    `/runs/${encodeURIComponent(id)}/fields/${encodeURIComponent(field)}/evidence-links/${encodeURIComponent(link)}`
  )
}
