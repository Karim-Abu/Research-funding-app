import { proxyToBridge } from "@/lib/bridge"

// GET /api/projects/{id}/state — Projekt-State (Requirements, Belege, …).
export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  return proxyToBridge(`/projects/${encodeURIComponent(id)}/state`)
}
