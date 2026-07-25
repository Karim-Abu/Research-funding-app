import { forwardToBridge } from "@/lib/bridge"

export async function POST(request: Request) {
  return forwardToBridge(request, "/system-status/connection-check")
}
