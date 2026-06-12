// Server-seitiger Helper für die Route-Handler unter app/api/*.
// Liest FASTAPI_BRIDGE_URL ausschließlich auf dem Server (nie NEXT_PUBLIC);
// der Wert erreicht den Client nicht. Antworten/Fehler folgen dem Envelope
// { error: { code, message } } mit deutschem message-Text.

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

/**
 * Proxy a request to the FastAPI bridge. Returns the bridge response body
 * verbatim; when the bridge URL is unset or the bridge does not answer,
 * returns 502 with the German error envelope.
 */
export async function proxyToBridge(
  path: string,
  init?: RequestInit
): Promise<NextResponse> {
  const base = process.env.FASTAPI_BRIDGE_URL
  if (!base) {
    return NextResponse.json(BRIDGE_UNREACHABLE, { status: 502 })
  }

  let res: Response
  try {
    res = await fetch(`${base.replace(/\/$/, "")}${path}`, {
      ...init,
      // Run requests must never be cached.
      cache: "no-store",
    })
  } catch {
    return NextResponse.json(BRIDGE_UNREACHABLE, { status: 502 })
  }

  // Stream the body through unchanged — also carries binary payloads
  // (e.g. the DOCX export); Content-Disposition is forwarded for downloads.
  const headers = new Headers()
  headers.set(
    "Content-Type",
    res.headers.get("Content-Type") ?? "application/json"
  )
  const disposition = res.headers.get("Content-Disposition")
  if (disposition) headers.set("Content-Disposition", disposition)

  return new NextResponse(res.body, { status: res.status, headers })
}
