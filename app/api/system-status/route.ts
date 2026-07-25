import { forwardToBridge } from "@/lib/bridge"

export async function GET(request: Request) {
  return forwardToBridge(request, "/system-status")
}
