import { forwardToBridge } from "@/lib/bridge"

// GET /api/health — Health-Check der Bridge (öffentlich).
export async function GET(request: Request) {
  return forwardToBridge(request, "/health")
}
