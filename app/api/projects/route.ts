import { forwardToBridge } from "@/lib/bridge"

// GET /api/projects — Projektliste; POST /api/projects — Projekt anlegen
// (CSRF + Idempotency-Key werden vom BFF durchgereicht).
export async function GET(request: Request) {
  return forwardToBridge(request, "/projects")
}

export async function POST(request: Request) {
  return forwardToBridge(request, "/projects")
}
