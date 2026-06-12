// Dummy-Daten für den Prototyp. Keine echten Daten, keine Backend-Aufrufe.
// Gates und Issues kommen aus dem Contract (lib/backend-contract.ts) bzw.
// dem Mock in lib/api.ts — hier leben nur noch Freigabe-Zustand und die
// Debug-Szenarien.

// ---------------------------------------------------------------------------
// Approval card state
// ---------------------------------------------------------------------------

export type ApprovalState =
  | "blocked"
  | "open"
  | "approved"
  | "stale"
  | "changes_requested"

export interface ApprovalData {
  state: ApprovalState
  approvedBy?: string
  approvedAt?: string
  changesRequestedBy?: string
  changesRequestedComment?: string
  selfReview?: boolean
}

export const DEFAULT_APPROVAL: ApprovalData = {
  state: "blocked",
  selfReview: true,
}

// ---------------------------------------------------------------------------
// Page scenario registry (for debug switcher)
// ---------------------------------------------------------------------------

export type PageScenario =
  | "default"
  | "all_clear"
  | "blocked"
  | "approved"
  | "stale"
  | "empty"
  | "stopped_run"
  | "changes_requested"

export interface ReviewScenario {
  id: PageScenario
  label: string
}

export const PAGE_SCENARIOS: ReviewScenario[] = [
  { id: "default", label: "Standard (Blocker)" },
  { id: "all_clear", label: "Alles OK" },
  { id: "approved", label: "Freigegeben" },
  { id: "stale", label: "Freigabe veraltet" },
  { id: "changes_requested", label: "Änderungen nötig" },
  { id: "empty", label: "Leer" },
  { id: "stopped_run", label: "Gestoppter Durchlauf" },
]
