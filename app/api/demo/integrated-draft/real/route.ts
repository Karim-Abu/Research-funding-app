import { forwardToBridge } from "@/lib/bridge"

// GET /api/demo/integrated-draft/real — read-only view over already generated
// R5.9-REAL artifacts (whitelist report part only). Never runs a provider call.
export async function GET(request: Request) {
  return forwardToBridge(request, "/demo/integrated-draft/real")
}
