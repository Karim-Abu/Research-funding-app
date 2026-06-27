// Server-seitiger Helper für die Route-Handler unter app/api/*.
// Liest FASTAPI_BRIDGE_URL ausschließlich auf dem Server (nie NEXT_PUBLIC);
// der Wert erreicht den Client nicht. Antworten/Fehler folgen dem Envelope
// { error: { code, message } } bzw. application/problem+json der Bridge.

import { NextResponse } from "next/server"

const BRIDGE_UNREACHABLE = {
  error: {
    code: "bridge_unreachable",
    message:
      "Der Analysedienst ist derzeit nicht erreichbar. Bitte versuchen Sie es später erneut.",
  },
} as const

const NOT_IMPLEMENTED = {
  error: {
    code: "not_implemented",
    message: "Diese Funktion ist noch nicht verfügbar.",
  },
} as const

export function notImplemented(): NextResponse {
  return NextResponse.json(NOT_IMPLEMENTED, { status: 501 })
}

// Header, die vom Browser an die Bridge weitergereicht werden (Session/CSRF).
const REQUEST_HEADERS_TO_FORWARD = [
  "cookie",
  "origin",
  "content-type",
  "x-csrf-token",
  "idempotency-key",
  "x-correlation-id",
]

// Header, die von der Bridge zurück an den Browser weitergereicht werden.
// NB: Content-Length is intentionally NOT forwarded — the body is streamed
// through Next.js (which sets its own framing), and a forwarded length can
// mismatch the re-framed stream and stall/truncate JSON responses.
const RESPONSE_HEADERS_TO_FORWARD = [
  "content-type",
  "content-disposition",
  "location",
  "retry-after",
  "x-correlation-id",
]

function buildResponse(res: Response): NextResponse {
  const headers = new Headers()
  for (const name of RESPONSE_HEADERS_TO_FORWARD) {
    const value = res.headers.get(name)
    if (value) headers.set(name, value)
  }
  // Jeden Set-Cookie-Header einzeln durchreichen (Session-Cookie der Bridge).
  const setCookies =
    typeof res.headers.getSetCookie === "function"
      ? res.headers.getSetCookie()
      : []
  for (const cookie of setCookies) headers.append("set-cookie", cookie)
  if (!headers.has("content-type")) {
    headers.set("content-type", "application/json")
  }
  return new NextResponse(res.body, { status: res.status, headers })
}

async function callBridge(
  path: string,
  init: RequestInit
): Promise<NextResponse> {
  const base = process.env.FASTAPI_BRIDGE_URL
  if (!base) {
    return NextResponse.json(BRIDGE_UNREACHABLE, { status: 502 })
  }
  let res: Response
  try {
    res = await fetch(`${base.replace(/\/$/, "")}${path}`, {
      ...init,
      // Run/auth requests must never be cached.
      cache: "no-store",
    })
  } catch {
    return NextResponse.json(BRIDGE_UNREACHABLE, { status: 502 })
  }
  return buildResponse(res)
}

/**
 * Proxy a request to the bridge with an explicit path + init (legacy handlers).
 * The response body is streamed through unchanged (also carries binary exports).
 */
export async function proxyToBridge(
  path: string,
  init?: RequestInit
): Promise<NextResponse> {
  return callBridge(path, init ?? {})
}

/**
 * Forward the incoming browser request (method, allow-listed headers, body, and
 * query string) to the bridge. Preserves Cookie/Origin/CSRF/Idempotency-Key so
 * the FastAPI session layer can authenticate and validate the request.
 */
export async function forwardToBridge(
  request: Request,
  path: string
): Promise<NextResponse> {
  const headers = new Headers()
  for (const name of REQUEST_HEADERS_TO_FORWARD) {
    const value = request.headers.get(name)
    if (value) headers.set(name, value)
  }

  let body: ArrayBuffer | undefined
  if (request.method !== "GET" && request.method !== "HEAD") {
    body = await request.arrayBuffer()
    if (body.byteLength === 0) body = undefined
  }

  const search = new URL(request.url).search
  return callBridge(`${path}${search}`, {
    method: request.method,
    headers,
    body,
  })
}
