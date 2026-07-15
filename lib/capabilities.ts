// Capabilities client — drives feature gating (e.g. URL import) and limits.

import { isLive } from "./app-mode"

export interface Capabilities {
  api_version: string
  polling_interval_seconds: number
  max_upload_bytes?: number | null
  supported_source_types: string[]
  features: Record<string, boolean>
  // "live_unavailable": Live-Betrieb konfiguriert, Provider nicht verfügbar —
  // nie ein stiller Abstieg auf den Demo-Generator (Ebene E).
  generation_mode?: "unavailable" | "fake_demo" | "real_eval" | "live_unavailable"
  generation_unavailable_reason?: string | null
}

export const MOCK_CAPABILITIES: Capabilities = {
  api_version: "1.1.0",
  polling_interval_seconds: 2,
  max_upload_bytes: 10 * 1024 * 1024,
  supported_source_types: ["pdf", "docx", "txt"],
  features: {
    projects: true,
    sources: true,
    source_parsing: true,
    url_import: false,
    partners: true,
    runs: true,
    requirements: true,
    evidence: true,
    drafts: true,
    review: false,
    export: false,
    web_research: false,
    market_comparison: false,
    reliability: false,
    // Mock mode never talks to the network — copy events stay off.
    copy_events: false,
  },
  generation_mode: "fake_demo",
  generation_unavailable_reason: null,
}

const UNAVAILABLE_CAPABILITIES: Capabilities = {
  ...MOCK_CAPABILITIES,
  generation_mode: "unavailable",
  generation_unavailable_reason: "capabilities_unavailable",
}

export async function getCapabilities(): Promise<Capabilities> {
  if (!isLive("capabilities")) return MOCK_CAPABILITIES
  try {
    const res = await fetch("/api/capabilities")
    if (!res.ok) return UNAVAILABLE_CAPABILITIES
    return (await res.json()) as Capabilities
  } catch {
    return UNAVAILABLE_CAPABILITIES
  }
}
