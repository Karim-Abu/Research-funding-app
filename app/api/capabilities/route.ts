import { forwardToBridge } from "@/lib/bridge"

// GET /api/capabilities — serverseitige Feature-/Rollen-Capabilities.
export async function GET(request: Request) {
  return forwardToBridge(request, "/capabilities")
}
