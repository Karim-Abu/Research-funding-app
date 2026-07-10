import { forwardToBridge } from "@/lib/bridge"

// POST /api/demo/integrated-draft — fake-only demo DraftPackage (DEMO.1).
// The backend refuses (503) unless the fake provider mode is enabled; a UI
// click can never trigger a real provider call.
export async function POST(request: Request) {
  return forwardToBridge(request, "/demo/integrated-draft")
}
