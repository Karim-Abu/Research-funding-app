import { proxyToBridge } from "@/lib/bridge"

// POST /api/feedback — anonymes Beta-Feedback (FeedbackDto).
export async function POST(request: Request) {
  const body = await request.text()
  return proxyToBridge("/feedback", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body,
  })
}
