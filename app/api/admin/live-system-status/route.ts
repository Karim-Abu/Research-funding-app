import { forwardToBridge } from "@/lib/bridge"

export async function GET(request: Request) {
  return forwardToBridge(request, "/admin/live-system-status")
}

export async function POST(request: Request) {
  return forwardToBridge(request, "/admin/live-system-status/preflight")
}
