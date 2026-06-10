// Dummy-Daten für "Kosten & Laufzeit". Keine echten Daten, keine Backend-Aufrufe.

export type RunStatus =
  | "completed"
  | "stopped_cost"
  | "failed"
  | "cancelled"

export type RunType = "analysis" | "section_regenerated" | "web_search"

export interface Run {
  id: string
  date: string
  type: RunType
  user: string
  kiEnabled: boolean
  webEnabled: boolean
  approximateCost: string // CHF, always shown as "~CHF x.xx"
  status: RunStatus
  // Detail-drawer only
  model: string
  tokensUsed: string
  stopReason?: string
  auditRef: string
}

export interface ServiceRow {
  id: string
  name: string
  configured: boolean
}

// -------------------------------------------------------------------------
// Usage (Dummy)
// -------------------------------------------------------------------------

export const USAGE = {
  usedChf: 86,
  limitChf: 200,
  perRunLimitChf: 20,
} as const

// -------------------------------------------------------------------------
// 8 Dummy runs
// -------------------------------------------------------------------------

export const RUNS: Run[] = [
  {
    id: "r1",
    date: "10. Juni 2026, 09:42",
    type: "analysis",
    user: "Anna Keller",
    kiEnabled: true,
    webEnabled: true,
    approximateCost: "~CHF 8.40",
    status: "completed",
    model: "Claude (Dummy)",
    tokensUsed: "45'000 Tokens (Dummy)",
    auditRef: "AE-2031 (Dummy)",
  },
  {
    id: "r2",
    date: "9. Juni 2026, 14:15",
    type: "analysis",
    user: "Tobias Frei",
    kiEnabled: true,
    webEnabled: false,
    approximateCost: "~CHF 6.90",
    status: "stopped_cost",
    model: "Claude (Dummy)",
    tokensUsed: "38'000 Tokens (Dummy)",
    stopReason: "Kostenlimit von CHF 20 erreicht. Bisherige Ergebnisse sind gespeichert.",
    auditRef: "AE-2030 (Dummy)",
  },
  {
    id: "r3",
    date: "8. Juni 2026, 11:03",
    type: "section_regenerated",
    user: "Anna Keller",
    kiEnabled: true,
    webEnabled: false,
    approximateCost: "~CHF 1.20",
    status: "completed",
    model: "Claude (Dummy)",
    tokensUsed: "6'500 Tokens (Dummy)",
    auditRef: "AE-2029 (Dummy)",
  },
  {
    id: "r4",
    date: "7. Juni 2026, 16:55",
    type: "web_search",
    user: "Anna Keller",
    kiEnabled: false,
    webEnabled: true,
    approximateCost: "~CHF 0.80",
    status: "completed",
    model: "— (Dummy)",
    tokensUsed: "— (Dummy)",
    auditRef: "AE-2028 (Dummy)",
  },
  {
    id: "r5",
    date: "6. Juni 2026, 10:30",
    type: "analysis",
    user: "Tobias Frei",
    kiEnabled: true,
    webEnabled: true,
    approximateCost: "~CHF 9.10",
    status: "failed",
    model: "Claude (Dummy)",
    tokensUsed: "12'000 Tokens (Dummy)",
    stopReason: "Dienst nicht erreichbar. Bitte erneut versuchen.",
    auditRef: "AE-2027 (Dummy)",
  },
  {
    id: "r6",
    date: "5. Juni 2026, 08:15",
    type: "section_regenerated",
    user: "Anna Keller",
    kiEnabled: true,
    webEnabled: false,
    approximateCost: "~CHF 1.60",
    status: "cancelled",
    model: "OpenAI (Dummy)",
    tokensUsed: "8'200 Tokens (Dummy)",
    stopReason: "Durch Nutzer:in abgebrochen.",
    auditRef: "AE-2026 (Dummy)",
  },
  {
    id: "r7",
    date: "4. Juni 2026, 15:20",
    type: "analysis",
    user: "Anna Keller",
    kiEnabled: true,
    webEnabled: true,
    approximateCost: "~CHF 7.70",
    status: "completed",
    model: "Claude (Dummy)",
    tokensUsed: "42'000 Tokens (Dummy)",
    auditRef: "AE-2025 (Dummy)",
  },
  {
    id: "r8",
    date: "3. Juni 2026, 13:05",
    type: "analysis",
    user: "Tobias Frei",
    kiEnabled: true,
    webEnabled: false,
    approximateCost: "~CHF 5.30",
    status: "completed",
    model: "OpenAI (Dummy)",
    tokensUsed: "29'000 Tokens (Dummy)",
    auditRef: "AE-2024 (Dummy)",
  },
]

// -------------------------------------------------------------------------
// Dienste (lead_admin only)
// -------------------------------------------------------------------------

export const SERVICES: ServiceRow[] = [
  { id: "svc-claude", name: "Claude", configured: true },
  { id: "svc-openai", name: "OpenAI", configured: true },
  { id: "svc-web", name: "Webrecherche (Firecrawl)", configured: false },
]
