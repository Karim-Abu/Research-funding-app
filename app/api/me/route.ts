import { forwardToBridge } from "@/lib/bridge"

// GET /api/me — aktueller Benutzer der Session.
export async function GET(request: Request) {
  return forwardToBridge(request, "/me")
}
