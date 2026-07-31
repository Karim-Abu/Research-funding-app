// A2 draft-suggestion client (Milestone 9D; extended to Value Creation in 9E).
// createRedraft (202 async) → poll the operation → the suggestion in result.
// Advisory only: accepting is a separate updateField call with source_operation_id.
// Scoped to the A2-enabled fields below. DraftProposal ist der neutrale View;
// Provider-/Modellmetadaten gibt es nur im kompatiblen AIProposal nach einem
// echten Modellaufruf und nur unter Technische Details.

import { getCsrfToken } from "./session"
import { pollOperation, type AsyncOperationDto } from "./operations"
import type { GenerationKind } from "./generation-kind"

export const SOLUTION_INNOVATION_FIELD_ID = "SOL.INNOVATION_SOLUTION.EDITOR"
export const VALUE_CREATION_FIELD_ID = "VC.BUSINESS_TARGETS_MODEL.EDITOR"
export const ABSTRACT_FIELD_ID = "INTRO.APP.ABSTRACT"
export const EXECUTIVE_SUMMARY_FIELD_ID = "INTRO.APP.EXECUTIVE_SUMMARY"
export const FINANCIAL_INDEPENDENCE_FIELD_ID = "ORG.INDEPENDENCE.FINANCIAL.EXPLANATIONS_COMMENTS"
export const MANAGEMENT_HOURS_EXPLANATION_FIELD_ID = "PS.PLANNED_HOURS.MANAGEMENT_EXPLANATION"

// The explicit set of fields that may request an A2 suggestion. Mirrors the
// backend registry-backed allow-list; the backend stays authoritative.
export const A2_FIELD_IDS: ReadonlySet<string> = new Set([
  SOLUTION_INNOVATION_FIELD_ID,
  VALUE_CREATION_FIELD_ID,
  ABSTRACT_FIELD_ID,
  EXECUTIVE_SUMMARY_FIELD_ID,
  FINANCIAL_INDEPENDENCE_FIELD_ID,
  MANAGEMENT_HOURS_EXPLANATION_FIELD_ID,
])

export function isA2Field(fieldId: string | undefined | null): boolean {
  return fieldId != null && A2_FIELD_IDS.has(fieldId)
}

export interface A2EvidenceItem {
  anchor_id: string
  quote: string
  source_name: string
  verification_status: string
  page?: number | null
  section?: string | null
}

export interface A2Placeholder {
  label: string
  reason?: string | null
}

export interface AIMissingInput {
  label: string
  reason?: string | null
}

// Typisierte Proposal-Views (Spiegel von backend/app/agents/proposal.py).
// human_review_required ist im Typ auf `true` fixiert: keine Auto-Übernahme.
export interface DraftProposal {
  suggestion_text: string
  used_anchor_ids: string[]
  used_research_source_ids: string[]
  missing_inputs: AIMissingInput[]
  profile_id: string
  prompt_version: string | null
  context_hash: string | null
  generation_kind?: GenerationKind | null
  model_ref?: string | null
  created_at: string
  data_mode: string
  provider?: string | null
  model?: string | null
  usage_record_id?: string | null
  safety_notes?: string[]
  human_review_required: true
}

export interface AIProposal extends DraftProposal {
  generation_kind: "model_generated"
  model_ref: string
  provider: string
  model: string
}

export interface SectionResult {
  field_id: string
  target_section: string
  suggested_text: string
  rationale: string
  // Die Listen sind nur bei Abschnitts-Vorschlägen (PortalSectionDraftBundle)
  // garantiert; Feld-Level-Vorschläge (PortalFieldDraftBundle) tragen sie
  // nicht — Konsumenten müssen mit fehlenden Listen umgehen (?? []).
  preserved_facts?: string[]
  removed_or_reframed_claims?: string[]
  new_claims?: string[]
  missing_inputs?: AIMissingInput[]
  evidence_anchor_ids?: string[]
  research_source_ids?: string[]
  open_issue_ids?: string[]
}

export interface A2Suggestion {
  suggestion_id: string
  operation_id: string
  field_id: string
  target_section?: string | null
  generation_kind?: GenerationKind | null
  execution_mode?: "live" | "fake_demo"
  base_version_id: string
  suggested_text: string
  rationale?: string | null
  evidence: A2EvidenceItem[]
  research_sources?: Array<{
    source_id: string
    title: string
    url: string
    research_module?: string | null
    support_status: "supports" | "partially_supports"
    content_review_status: "reviewed"
  }>
  open_issue_ids: string[]
  placeholders: A2Placeholder[]
  character_count: number
  character_limit: number
  warnings: string[]
  section_result?: SectionResult | null
  proposal?: DraftProposal
  ai_proposal?: AIProposal
  manifest_id?: string | null
  improvement_mode?: ImprovementMode | null
  change_summary?: string[]
  used_rule_ids?: string[]
  missing_inputs?: Array<AIMissingInput & { key: string; requirement_ids: string[] }>
  unsupported_claim_warnings?: string[]
  source_version_ids?: string[]
  market_comparison_id?: string | null
  context_hash?: string | null
  quality_state?: "completed" | "completed_with_warnings" | "needs_input" | null
  stale_reason?: string | null
  accept_mode?: "legacy_partial" | "whole_suggestion_only"
}

export type ImprovementMode =
  | "clearer"
  | "complete_innolink_requirements"
  | "shorten"

export interface SuggestionContextAnchorOption {
  anchor_id: string
  source_id: string
  source_version_id: string
  source_name: string
  scope: "external" | "drafting_context"
  verification_status: "exact_verified" | "human_verified"
  page?: number | null
  section?: string | null
}

export interface SuggestionContextOptions {
  anchors: SuggestionContextAnchorOption[]
  market_comparison_id?: string | null
  market_comparison_status?: string | null
}

function idempotencyKey(): string {
  return crypto.randomUUID().replace(/-/g, "")
}

export function parseDraftProposal(value: unknown): DraftProposal | null {
  if (typeof value !== "object" || value === null) return null
  const v = value as Record<string, unknown>
  if (typeof v.suggestion_text !== "string" || typeof v.profile_id !== "string") return null
  if (v.human_review_required !== true) return null
  if (!Array.isArray(v.used_anchor_ids) || !Array.isArray(v.missing_inputs)) return null
  if (v.used_research_source_ids != null && !Array.isArray(v.used_research_source_ids)) return null
  if (
    v.generation_kind != null &&
    !["rule_template", "fake_demo", "model_generated"].includes(String(v.generation_kind))
  ) return null
  return v as unknown as DraftProposal
}

/** Fail-closed AIProposal-Parser: ungültige/fremde Shapes ⇒ null. */
export function parseAIProposal(value: unknown): AIProposal | null {
  if (typeof value !== "object" || value === null) return null
  const v = value as Record<string, unknown>
  const requiredStrings = [
    "suggestion_text", "profile_id", "model_ref", "created_at",
    "data_mode", "provider", "model",
  ] as const
  if (requiredStrings.some((k) => typeof v[k] !== "string")) return null
  if (v.generation_kind !== "model_generated") return null
  if (v.human_review_required !== true) return null
  if (!Array.isArray(v.used_anchor_ids) || !Array.isArray(v.missing_inputs)) return null
  return v as unknown as AIProposal
}

export class RedraftError extends Error {
  readonly status: number
  readonly code: string
  /** R4.2: maschinenlesbarer Verfügbarkeits-Blockgrund (Katalog-Code) oder null. */
  readonly reasonCode: string | null
  /** Transienter Providerfehler auf der Primärroute — die UI darf zusätzlich
   *  «Mit alternativem Modell versuchen» anbieten (nie bei Policy/Schema/Budget). */
  readonly retryWithAlternativeModel: boolean
  constructor(
    status: number,
    code: string,
    message: string,
    reasonCode: string | null = null,
    retryWithAlternativeModel = false
  ) {
    super(message)
    this.name = "RedraftError"
    this.status = status
    this.code = code
    this.reasonCode = reasonCode
    this.retryWithAlternativeModel = retryWithAlternativeModel
  }
}

// R4.2 — Owner-approved Microcopy je Reason-Code (docs/repair/message-catalog.md
// §R4.2). Text und CTA-Label sind freigegeben; Änderungen laufen über den Katalog.
// Ohne ctaLabel rendert der Hinweis bewusst ohne Aktion (z. B. field_not_supported:
// es gibt dort keine echte Aktion — Katalog-Update 2026-07-23).
export interface AiReasonInfo {
  text: string
  ctaLabel?: string
}

export const AI_REASON_INFO: Record<string, AiReasonInfo> = {
  nda_locked: {
    text: "Für gesperrte/NDA-Daten sind KI-Vorschläge deaktiviert.",
    ctaLabel: "Verarbeitungsmodus prüfen",
  },
  mode_deterministic_only: {
    text: "Dieses Projekt ist aktuell auf regelbasierte Verarbeitung beschränkt.",
    ctaLabel: "Verarbeitungsmodus ändern",
  },
  provider_unavailable: {
    text: "Für diese Datenklasse ist aktuell kein freigegebener KI-Provider konfiguriert. Die App führt nur regelbasierte Prüfungen aus.",
    ctaLabel: "Provider-Konfiguration prüfen",
  },
  live_provider_key_missing: {
    text: "KI-Vorschläge sind derzeit nicht verfügbar. Prüfen Sie den Systemstatus oder wenden Sie sich an einen Lead-Admin.",
    ctaLabel: "Systemstatus öffnen",
  },
  live_fake_conflict: {
    text: "KI-Vorschläge sind wegen einer widersprüchlichen Konfiguration nicht verfügbar. Ein Lead-Admin kann die Verbindung im Systemstatus prüfen.",
    ctaLabel: "Systemstatus öffnen",
  },
  live_eval_mode_disabled: {
    text: "KI-Vorschläge sind derzeit deaktiviert. Ein Lead-Admin kann den Status der Verbindung prüfen.",
    ctaLabel: "Systemstatus öffnen",
  },
  live_model_id_missing: {
    text: "KI-Vorschläge sind nicht vollständig eingerichtet. Prüfen Sie den Systemstatus oder wenden Sie sich an einen Lead-Admin.",
    ctaLabel: "Systemstatus öffnen",
  },
  live_price_metadata_missing: {
    text: "Live-KI ist nicht verfügbar. Ergänzen Sie geprüfte Preis-Metadaten für die konkrete Modell-ID.",
    ctaLabel: "Systemstatus öffnen",
  },
  live_preflight_required: {
    text: "KI-Vorschläge sind noch nicht verfügbar. Ein Lead-Admin kann die Verbindung im Systemstatus prüfen.",
    ctaLabel: "Systemstatus öffnen",
  },
  live_preflight_expired: {
    text: "Die letzte Verbindungsprüfung ist nicht mehr aktuell. Ein Lead-Admin kann sie im Systemstatus wiederholen.",
    ctaLabel: "Systemstatus öffnen",
  },
  live_preflight_failed: {
    text: "Die letzte Verbindungsprüfung war nicht erfolgreich. Ein Lead-Admin kann die Verbindung im Systemstatus erneut prüfen.",
    ctaLabel: "Systemstatus öffnen",
  },
  live_preflight_stale_model: {
    text: "Die KI-Konfiguration wurde seit der letzten Prüfung geändert. Ein Lead-Admin kann sie im Systemstatus erneut prüfen.",
    ctaLabel: "Systemstatus öffnen",
  },
  live_actual_model_missing: {
    text: "Die KI-Verbindung konnte nicht vollständig bestätigt werden. Prüfen Sie den Systemstatus.",
    ctaLabel: "Systemstatus öffnen",
  },
  no_approved_model_provider: {
    text: "Es ist kein freigegebener KI-Provider aktiv. Die App führt nur regelbasierte Prüfungen aus.",
    ctaLabel: "Provider-Konfiguration prüfen",
  },
  run_mode_mismatch: {
    text: "Der aktuelle Analysemodus passt nicht zum Feldvorschlag.",
    ctaLabel: "Analysemodus prüfen",
  },
  missing_sources: {
    text: "Für einen belastbaren Vorschlag fehlen passende Quellen.",
    ctaLabel: "Quelle hinzufügen",
  },
  field_not_supported: {
    text: "Für dieses Feld ist noch kein Abschnittsvorschlag verfügbar.",
  },
  // CostGuard: deterministisches Aufruf-Limit des Analyse-Laufs — Wiederholen
  // im selben Lauf kann nie gelingen, die Aktion ist ein neuer Lauf.
  ai_call_limit_reached: {
    text: "Das Limit für KI-Aufrufe in diesem Analyse-Lauf ist erreicht. Starten Sie einen neuen Analyse-Lauf, um weitere Vorschläge zu erzeugen.",
  },
}

/** Fail-closed-Anzeige, wenn ein 503 ohne bekannten Code eintrifft. */
export const FALLBACK_AI_REASON = "provider_unavailable"

// RUN 4B §4 — Klartext je Staleness-Grund (kanonische Codes aus
// backend/app/agents/suggestion_staleness.py + Legacy stale_base_version).
// Reine Anzeige-Strings; die Prüfung bleibt serverseitig.
export const STALE_REASON_LABELS: Record<string, string> = {
  draft_version_changed: "Der Abschnitt wurde seit diesem Vorschlag geändert.",
  context_manifest_missing:
    "Der Kontext dieses Vorschlags ist nicht mehr verfügbar.",
  run_snapshot_changed: "Die Projektdaten wurden seither aktualisiert.",
  primary_application_version_changed:
    "Das zugrunde liegende Antragsdokument wurde aktualisiert.",
  registry_version_changed:
    "Die Innolink-Anforderungsliste wurde aktualisiert.",
  field_instruction_changed:
    "Die Vorgaben für dieses Feld haben sich geändert.",
  anchor_changed: "Eine verwendete Fundstelle ist nicht mehr bestätigt.",
  source_version_changed: "Eine verwendete Quelle liegt in neuer Version vor.",
  market_comparison_changed: "Der Marktvergleich wurde seither aktualisiert.",
  stale_base_version: "Der Abschnitt wurde seit diesem Vorschlag geändert.",
}

export function staleReasonLabel(
  reason: string | null | undefined
): string | null {
  if (!reason) return null
  return (
    STALE_REASON_LABELS[reason] ??
    "Dieser Vorschlag basiert nicht mehr auf dem aktuellen Stand."
  )
}

const MESSAGES: Record<string, string> = {
  stale_base_version: "Dieser Abschnitt wurde zwischenzeitlich geändert.",
  // Qualitäts-Gates: die KI-Antwort wurde serverseitig verworfen — ehrlich
  // benennen statt Generiktext; ein erneuter Versuch kann gelingen.
  failed_grounding_validation:
    "Der Vorschlag enthielt konkrete Aussagen ohne Grundlage in Ihren Angaben und wurde verworfen. Ein erneuter Versuch kann gelingen.",
  unknown_evidence_anchor:
    "Der Vorschlag verwies auf nicht freigegebene Belege und wurde verworfen. Ein erneuter Versuch kann gelingen.",
  unknown_open_issue:
    "Der Vorschlag verwies auf unbekannte offene Punkte und wurde verworfen. Ein erneuter Versuch kann gelingen.",
  unknown_research_source:
    "Der Vorschlag verwies auf nicht freigegebene Quellen und wurde verworfen. Ein erneuter Versuch kann gelingen.",
  new_claim_without_source:
    "Der Vorschlag enthielt neue Aussagen ohne Quelle und wurde verworfen. Ein erneuter Versuch kann gelingen.",
  invented_patent_identifier:
    "Der Vorschlag enthielt nicht belegte Schutzrechtsangaben und wurde verworfen.",
  invented_numeric_token:
    "Der Vorschlag enthielt nicht belegte Zahlenangaben und wurde verworfen.",
  invented_partner_name:
    "Der Vorschlag enthielt nicht belegte Organisationsnamen und wurde verworfen.",
  character_limit_exceeded:
    "Der Vorschlag überschritt das Zeichenlimit des Felds und wurde verworfen. Ein erneuter Versuch kann gelingen.",
  empty_suggested_text:
    "Die KI lieferte keinen verwendbaren Text. Ein erneuter Versuch kann gelingen.",
  initial_draft_too_thin:
    "Die KI lieferte keinen substanziellen Erst-Entwurf und der Vorschlag wurde verworfen. Ein erneuter Versuch kann gelingen.",
  // Beleg-Auswahl: deterministisch vom Nutzer behebbar (kein Retry sinnvoll).
  selected_anchor_not_verified:
    "Ein gewählter Beleg ist nicht bestätigt. Passen Sie die Beleg-Auswahl an oder bestätigen Sie den Beleg zuerst.",
  selected_anchor_source_version_stale:
    "Ein gewählter Beleg stammt aus einer veralteten Quellenversion. Passen Sie die Beleg-Auswahl an.",
  selected_anchor_review_required:
    "Die Quelle eines gewählten Belegs ist noch nicht inhaltlich geprüft. Passen Sie die Beleg-Auswahl an.",
  selected_anchor_quarantined:
    "Die Quelle eines gewählten Belegs ist nicht freigegeben. Passen Sie die Beleg-Auswahl an.",
  unknown_selected_anchor:
    "Ein gewählter Beleg existiert nicht mehr. Passen Sie die Beleg-Auswahl an.",
}

// 2026-07-24 — deterministische Abschnittsstruktur-Fehler (Katalog-Addendum,
// docs/repair/message-catalog.md). Präfix-Codes tragen den betroffenen Marker
// nach dem Doppelpunkt (z. B. «section_marker_missing:4.5.2»).
const REDRAFT_FAILURE_LABELS: Record<string, (marker: string) => string> = {
  section_marker_missing: (marker) =>
    `Die Markerzeile «${marker}» fehlt im Text. Stellen Sie die Zeile «${marker}» wieder her oder wählen Sie einen vorhandenen Zielabschnitt.`,
  section_marker_ambiguous: (marker) =>
    `Die Markerzeile «${marker}» kommt mehrfach vor. Entfernen Sie die doppelte Zeile, damit der Abschnitt eindeutig bleibt.`,
  section_markers_out_of_order: () =>
    "Die Abschnittsmarker stehen nicht in der Reihenfolge der Vorlage. Ordnen Sie die Abschnitte wieder aufsteigend.",
  section_target_unknown: () =>
    "Der gewählte Abschnitt ist für dieses Feld nicht verfügbar. Bitte wählen Sie einen gültigen Zielabschnitt.",
  section_markers_missing: () =>
    "Der gewählte Abschnitt ist für dieses Feld nicht verfügbar. Bitte wählen Sie einen gültigen Zielabschnitt.",
}

export function redraftFailureLabel(code: string): string | null {
  const separator = code.indexOf(":")
  const prefix = separator === -1 ? code : code.slice(0, separator)
  const marker = separator === -1 ? "" : code.slice(separator + 1)
  const build = REDRAFT_FAILURE_LABELS[prefix]
  return build ? build(marker) : null
}

/** Deterministisch = vom Nutzer behebbar; ein erneuter Versuch ohne
 *  Text-/Auswahländerung kann nie gelingen — die UI bietet dann kein
 *  «Erneut versuchen» an. */
export function isDeterministicRedraftFailure(code: string): boolean {
  return (
    code.startsWith("section_") ||
    code.startsWith("selected_anchor_") ||
    code === "unknown_selected_anchor"
  )
}

function reasonMessage(reasonCode: string | null): string | null {
  return reasonCode ? (AI_REASON_INFO[reasonCode]?.text ?? null) : null
}

function csrfHeaders(): Record<string, string> {
  const csrf = getCsrfToken()
  return csrf ? { "X-CSRF-Token": csrf } : {}
}

async function toError(res: Response): Promise<RedraftError> {
  let code = "error"
  let reasonCode: string | null = null
  try {
    const body = await res.json()
    if (body?.code) code = body.code
    if (typeof body?.reason_code === "string") reasonCode = body.reason_code
  } catch {
    /* non-JSON */
  }
  const message =
    MESSAGES[code] ??
    redraftFailureLabel(code) ??
    reasonMessage(reasonCode) ??
    "Der Vorschlag konnte nicht erstellt werden."
  return new RedraftError(res.status, code, message, reasonCode)
}

/** Offene (proposed) Suggestion zur aktuellen Basisversion — z. B. aus dem
 *  normalen Analyse-Lauf erzeugt. Read-only; null, wenn keine vorliegt. */
export async function getRunFieldSuggestion(
  runId: string,
  fieldId: string,
  targetSection?: string
): Promise<A2Suggestion | null> {
  const query = targetSection
    ? `?target_section=${encodeURIComponent(targetSection)}`
    : ""
  const res = await fetch(
    `/api/runs/${encodeURIComponent(runId)}/fields/${encodeURIComponent(fieldId)}/suggestion${query}`
  )
  if (!res.ok) throw await toError(res)
  const body = (await res.json()) as { suggestion: Record<string, unknown> | null }
  if (!body.suggestion) return null
  const base = body.suggestion as unknown as A2Suggestion
  const proposal = parseDraftProposal(body.suggestion.proposal)
  const aiProposal = parseAIProposal(body.suggestion.ai_proposal)
  return {
    ...base,
    proposal: proposal ?? undefined,
    ai_proposal: aiProposal ?? undefined,
  }
}

/** Request a suggestion and resolve once the async operation produces it.
 *  modelPreference "alternative" = explizit angeforderte Alternativroute nach
 *  transientem Providerfehler — nie ein stiller automatischer Fallback. */
export async function createRedraft(
  runId: string,
  fieldId: string,
  baseVersionId: string,
  guidance?: string,
  targetSection?: string,
  modelPreference?: "primary" | "alternative",
  options: {
    improvementMode?: ImprovementMode
    selectedAnchorIds?: string[]
    language?: "de" | "en"
    idempotencyKey?: string
  } = {}
): Promise<A2Suggestion> {
  const requestKey = options.idempotencyKey ?? idempotencyKey()
  const res = await fetch(
    `/api/runs/${encodeURIComponent(runId)}/fields/${encodeURIComponent(fieldId)}/redrafts`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": requestKey,
        ...csrfHeaders(),
      },
      body: JSON.stringify({
        base_version_id: baseVersionId,
        ...(guidance ? { guidance } : {}),
        ...(targetSection ? { target_section: targetSection } : {}),
        ...(modelPreference && modelPreference !== "primary"
          ? { model_preference: modelPreference }
          : {}),
        improvement_mode: options.improvementMode ?? "clearer",
        selected_anchor_ids: options.selectedAnchorIds ?? [],
        ...(options.language ? { language: options.language } : {}),
      }),
    }
  )
  // 503 (unavailable) / 409 (stale base) are surfaced synchronously and safely.
  if (!res.ok) throw await toError(res)
  const accepted = (await res.json()) as { operation_id: string }

  return new Promise<A2Suggestion>((resolve, reject) => {
    pollOperation(accepted.operation_id, {
      onTerminal: (op: AsyncOperationDto) => {
        if (op.status === "succeeded" && op.result) {
          const base = op.result as unknown as A2Suggestion
          const proposal = parseDraftProposal(
            (op.result as Record<string, unknown>).proposal
          )
          const aiProposal = parseAIProposal(
            (op.result as Record<string, unknown>).ai_proposal
          )
          resolve({
            ...base,
            proposal: proposal ?? undefined,
            ai_proposal: aiProposal ?? undefined,
          })
        } else {
          const code = op.error?.code ?? "redraft_failed"
          const reasonCode = op.error?.reason_code ?? null
          reject(
            new RedraftError(
              500,
              code,
              MESSAGES[code] ??
                redraftFailureLabel(code) ??
                reasonMessage(reasonCode) ??
                "Der Vorschlag konnte nicht erstellt werden.",
              reasonCode,
              op.error?.retry_with_alternative_model === true
            )
          )
        }
      },
    })
  })
}

export async function getSuggestionContextOptions(
  runId: string,
  fieldId: string
): Promise<SuggestionContextOptions> {
  const res = await fetch(
    `/api/runs/${encodeURIComponent(runId)}/fields/${encodeURIComponent(fieldId)}/suggestion-context-options`
  )
  if (!res.ok) throw await toError(res)
  return (await res.json()) as SuggestionContextOptions
}

export async function acceptFieldSuggestion(
  runId: string,
  fieldId: string,
  suggestionId: string,
  baseVersionId: string,
  requestKey = idempotencyKey()
): Promise<{ suggestion_id: string; draft_version_id: string; status: "accepted"; idempotent_replay: boolean }> {
  const res = await fetch(
    `/api/runs/${encodeURIComponent(runId)}/fields/${encodeURIComponent(fieldId)}/suggestions/${encodeURIComponent(suggestionId)}/accept`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": requestKey,
        ...csrfHeaders(),
      },
      body: JSON.stringify({ base_version_id: baseVersionId }),
    }
  )
  if (!res.ok) throw await toError(res)
  return await res.json()
}
