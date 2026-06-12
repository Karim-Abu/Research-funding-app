import { proxyToBridge } from "@/lib/bridge"

// POST /api/sources — Datei-Upload (multipart) an die Bridge.
// Beta: die UI lässt nur .txt/.md zu; die Bridge validiert serverseitig erneut.
export async function POST(request: Request) {
  const form = await request.formData()
  return proxyToBridge("/sources", { method: "POST", body: form })
}
