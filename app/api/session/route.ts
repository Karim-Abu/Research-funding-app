import { forwardToBridge } from "@/lib/bridge"

// /api/session — Login (POST), Session-Bootstrap (GET), Logout (DELETE).
// Cookie/CSRF/Origin werden vom BFF an die FastAPI-Bridge durchgereicht.
export async function POST(request: Request) {
  return forwardToBridge(request, "/session")
}

export async function GET(request: Request) {
  return forwardToBridge(request, "/session")
}

export async function DELETE(request: Request) {
  return forwardToBridge(request, "/session")
}
