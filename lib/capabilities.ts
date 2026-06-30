// Capabilities client — drives feature gating (e.g. URL import) and limits.

import { isLive } from "./app-mode"

export interface Capabilities {
  api_version: string
  polling_interval_seconds: number
  max_upload_bytes?: number | null
  supported_source_types: string[]
  features: Record<string, boolean>
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
  },
}

export async function getCapabilities(): Promise<Capabilities> {
  if (!isLive("capabilities")) return MOCK_CAPABILITIES
  try {
    const res = await fetch("/api/capabilities")
    if (!res.ok) return MOCK_CAPABILITIES
    return (await res.json()) as Capabilities
  } catch {
    return MOCK_CAPABILITIES
  }
}
