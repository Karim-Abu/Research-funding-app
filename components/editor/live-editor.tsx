"use client"

import * as React from "react"
import Link from "next/link"
import { ExternalLink, Link2, RefreshCw, Sparkles, Trash2 } from "lucide-react"
import { Button, buttonVariants } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { Textarea } from "@/components/ui/textarea"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog"
import {
  listFields,
  getField,
  getFieldVersion,
  listFieldVersions,
  updateField,
  createEvidenceLink,
  deleteEvidenceLink,
  charCount,
  FieldError,
  type DraftVersionSummaryDto,
  type PortalFieldDraftDto,
} from "@/lib/fields"
import {
  listEvidence,
  formatFundstelle,
  EVIDENCE_LINK_STATUS_LABELS,
  EVIDENCE_SOURCE_TYPE_LABELS,
  type EvidenceAnchorDto,
} from "@/lib/evidence"
import { supportStatusFromVerification } from "@/lib/evidence-ladder"
import { SupportStatusBadge } from "@/components/status/support-status-badge"
import { listPortalFields, type PortalFieldInfoDto } from "@/lib/portal-fields"
import { placeholderMatches } from "@/lib/draft-view"
import { isPlaceholderOnly } from "@/lib/placeholders"
import {
  getReview,
  createHumanDecision,
  createApproval,
  ReviewError,
  type ReviewPackageDto,
  type ReviewFindingDto,
} from "@/lib/review"
import {
  isAiFinding,
  COMMENT_TYPES,
  commentWithType,
  parseCommentType,
  type CommentType,
} from "@/lib/review-view"
import {
  listRequirements,
  type RequirementAssessmentDto,
} from "@/lib/requirements"
import {
  liveStatusToBucket,
  REQ_FALLBACK,
  EVIDENCE_STATE_LABELS,
  HUMAN_STATE_LABELS,
} from "@/lib/requirements-view"
import { ReqBucketBadge } from "@/components/anforderungen/requirements-controls"
import type { RichTextEditorHandle } from "@/components/editor/rich-text-editor"
import { capabilitiesSelfHealing, getCapabilities, type Capabilities } from "@/lib/capabilities"
import {
  getLatestComparison,
  type MarketComparisonDto,
} from "@/lib/market-comparison"
import { DraftWorkspaceShell } from "@/components/editor/draft-workspace-shell"
import { AssistantPanel } from "@/components/editor/assistant-panel"
import { SuggestionReviewDialog } from "@/components/editor/suggestion-review-dialog"
import { MarketComparisonSheet } from "@/components/editor/market-comparison-sheet"
import { getActiveProjectId, loadIntake } from "@/lib/intake-store"
import {
  liveFieldToViewModel,
  pickDefaultTab,
  versionOriginLabel,
  type AssistantTab,
} from "@/lib/draft-viewmodel"
import {
  AI_REASON_INFO,
  acceptFieldSuggestion,
  createRedraft,
  FALLBACK_AI_REASON,
  getRunFieldSuggestion,
  getSuggestionContextOptions,
  isA2Field,
  isDeterministicRedraftFailure,
  RedraftError,
  redraftFailureLabel,
  SOLUTION_INNOVATION_FIELD_ID,
  VALUE_CREATION_FIELD_ID,
  type A2Suggestion,
  type ImprovementMode,
  type SuggestionContextOptions,
} from "@/lib/redraft"
import { getResearchWorkspace } from "@/lib/research-brief"
import {
  GENERATION_KIND_BADGE_CLASS,
  generationActionLabel,
  generationLabel,
  type GenerationKind,
} from "@/lib/generation-kind"
import { buildOutline, subsectionContent, subsectionText } from "@/lib/subsections"

type SaveState = "saved" | "dirty" | "saving" | "error"

// R4.2 — jeder KI-Blockgrund nennt Grund + Ausweg. Navigations-CTAs führen zur
// Quellen-/Analyseseite (Datenklasse, Analyse-Einstellungen, Quellen hinzufügen);
// Live-Blockgründe führen zum verständlichen Systemstatus — nie zu einem
// stillen Demo-Ersatz.
const REASON_CTA_HREF: Record<string, string> = {
  nda_locked: "/quellen",
  mode_deterministic_only: "/quellen",
  run_mode_mismatch: "/quellen",
  missing_sources: "/quellen",
  live_provider_key_missing: "/systemstatus",
  live_fake_conflict: "/systemstatus",
  live_eval_mode_disabled: "/systemstatus",
  live_model_id_missing: "/systemstatus",
  live_price_metadata_missing: "/systemstatus",
  live_preflight_required: "/systemstatus",
  live_preflight_expired: "/systemstatus",
  live_preflight_failed: "/systemstatus",
  live_preflight_stale_model: "/systemstatus",
  live_actual_model_missing: "/systemstatus",
}

function A2ReasonNotice({ reason }: { reason: string }) {
  const [adminHintOpen, setAdminHintOpen] = React.useState(false)
  const info = AI_REASON_INFO[reason] ?? AI_REASON_INFO[FALLBACK_AI_REASON]
  const href = REASON_CTA_HREF[reason]
  return (
    <div className="flex flex-col gap-1.5" data-reason-code={reason}>
      <p role="status" className="text-xs text-muted-foreground">
        {info.text}
      </p>
      {/* Ohne ctaLabel bewusst keine Aktion — ein Button ohne echte Wirkung
          (ehemals «Strukturvorlage nutzen») wäre irreführend. */}
      {info.ctaLabel ? (
        href ? (
          <Link
            href={href}
            className={cn(
              buttonVariants({ variant: "outline", size: "sm" }),
              "self-start"
            )}
          >
            {info.ctaLabel}
          </Link>
        ) : (
          <>
            <Button
              size="sm"
              variant="outline"
              className="self-start"
              onClick={() => setAdminHintOpen((v) => !v)}
            >
              {info.ctaLabel}
            </Button>
            {adminHintOpen && (
              <p className="text-xs text-muted-foreground">
                Ein freigegebener KI-Provider muss durch Ihre Administration
                konfiguriert werden. Alle übrigen Funktionen bleiben verfügbar.
              </p>
            )}
          </>
        )
      ) : null}
    </div>
  )
}

const RECHECK_NOTICE =
  "Änderungen gespeichert. Eine erneute Prüfung ist vor der Freigabe erforderlich."
const ACCEPT_NOTICE =
  "Text übernommen – Qualitätsprüfung erneut erforderlich."
// Ein Satz sichtbar; die Wirkungskette steht im Aufklapper darunter (R1).
const LINK_EXPLANATION =
  "Eine Verknüpfung ordnet diesem Entwurf eine Fundstelle zu — sie bestätigt nicht den gesamten Text."
const LINK_EXPLANATION_DETAILS =
  "Verknüpfte Fundstellen fliessen in die Evidenz-Prüfbereiche (Abdeckung und Suffizienz), die Zuverlässigkeitsprüfung und die Kopierbereitschaft dieses Felds ein."
const STALE_LINK_NOTICE =
  "Belege müssen für diese Textversion erneut geprüft werden."
// Wie viele wählbare Belege ohne Aufklappen sichtbar sind.
const ANCHOR_PREVIEW_COUNT = 5

const SAVE_STATE_LABEL: Record<SaveState, string> = {
  saving: "Speichert …",
  dirty: "Änderungen",
  error: "Fehler",
  saved: "Gespeichert",
}

export function LiveEditor({
  runId,
  initialFieldId,
}: {
  runId: string
  /** Deep link (?field=…): preselect and focus this portal field on load. */
  initialFieldId?: string | null
}) {
  // M9I-B: the active project drives the read-only market-comparison context.
  const marketProjectId = getActiveProjectId() ?? undefined
  // R4.4: Datenklasse für das Format-Cache-Gate — fehlt jedes Signal, bleibt
  // der Cache fail-closed deaktiviert (isRichCacheAllowed(undefined) = false).
  const workspaceDataClass = loadIntake()?.vertraulichkeit || undefined
  const [fields, setFields] = React.useState<PortalFieldDraftDto[] | null>(null)
  const [anchors, setAnchors] = React.useState<EvidenceAnchorDto[]>([])
  // R6: Registry-Katalog für die Unterabschnitts-Gliederung der Composite-Felder.
  const [portalCatalog, setPortalCatalog] = React.useState<PortalFieldInfoDto[]>([])
  const [requirements, setRequirements] = React.useState<
    RequirementAssessmentDto[] | null
  >(null)
  const [selectedId, setSelectedId] = React.useState<string | null>(null)
  const [localText, setLocalText] = React.useState("")
  const [baseVersionId, setBaseVersionId] = React.useState("")
  const [saveState, setSaveState] = React.useState<SaveState>("saved")
  const [errorMsg, setErrorMsg] = React.useState<string | null>(null)
  const [conflict, setConflict] = React.useState(false)
  // Unterscheidet den Hinweis nach Speichern («saved») von dem nach einer
  // Vorschlags-Übernahme («accepted»); null = kein Hinweis.
  const [recheck, setRecheck] = React.useState<null | "saved" | "accepted">(null)
  const [loadError, setLoadError] = React.useState<string | null>(null)
  const [review, setReview] = React.useState<ReviewPackageDto | null>(null)
  const [commentText, setCommentText] = React.useState("")
  const [commentType, setCommentType] = React.useState<CommentType>("Hinweis")
  const [confirmResolveId, setConfirmResolveId] = React.useState<string | null>(null)
  const [fieldNotice, setFieldNotice] = React.useState<string | null>(null)
  // B5 — Rückmeldung des «In Notizen verschieben»-Flows (unter dem Editor).
  const [notesNotice, setNotesNotice] = React.useState<string | null>(null)
  // Controlled assistant tab — lets review hints open the Belege tab directly.
  const [assistantTab, setAssistantTab] = React.useState<AssistantTab | null>(null)
  // Die Beleg-Auswahl bleibt standardmässig kurz (R4); der Rest auf Anforderung.
  const [showAllAnchors, setShowAllAnchors] = React.useState(false)
  // M10.3: live market comparison for the Markt tab + wide sheet.
  const [caps, setCaps] = React.useState<Capabilities | null>(null)
  const [comparison, setComparison] = React.useState<MarketComparisonDto | null>(null)
  const [comparisonLoaded, setComparisonLoaded] = React.useState(false)
  const [marketSheetOpen, setMarketSheetOpen] = React.useState(false)
  // M9D/9E: A2 draft suggestions (Solution & Innovation + Value Creation fields).
  const [a2Suggestion, setA2Suggestion] = React.useState<A2Suggestion | null>(null)
  const [a2Loading, setA2Loading] = React.useState(false)
  // R4.2: statt Boolean der konkrete Blockgrund (Katalog-Code) oder null.
  const [a2UnavailableReason, setA2UnavailableReason] = React.useState<
    string | null
  >(null)
  const [a2Error, setA2Error] = React.useState<string | null>(null)
  // Deterministische Fehler (z. B. fehlende Markerzeile) sind nur durch eine
  // Textänderung behebbar — «Erneut versuchen» wäre dort irreführend.
  const [a2ErrorRetryable, setA2ErrorRetryable] = React.useState(true)
  // Transienter Providerfehler auf der Primärroute: zusätzlich zur
  // Wiederholung darf explizit die Alternativroute angeboten werden.
  const [a2RetryAlternative, setA2RetryAlternative] = React.useState(false)
  const [a2ReviewOpen, setA2ReviewOpen] = React.useState(false)
  const [a2Accepting, setA2Accepting] = React.useState(false)
  // True, wenn der angezeigte Vorschlag aus dem Analyse-Lauf stammt (statt
  // aus einem manuellen «KI-Vorschlag erstellen»).
  const [a2FromRun, setA2FromRun] = React.useState(false)
  const [a2ImprovementMode, setA2ImprovementMode] = React.useState<ImprovementMode>("clearer")
  const [a2ContextOptions, setA2ContextOptions] = React.useState<SuggestionContextOptions | null>(null)
  const [a2SelectedAnchors, setA2SelectedAnchors] = React.useState<ReadonlySet<string>>(new Set())
  const [a2ContextLoading, setA2ContextLoading] = React.useState(false)
  // Die Belegauswahl ist optional und bleibt eingeklappt, bis sie gebraucht wird.
  const [a2AnchorsOpen, setA2AnchorsOpen] = React.useState(false)
  const [selectedSubsection, setSelectedSubsection] = React.useState<string | null>(null)
  // RUN 4B §9 — Versionshistorie des aktiven Feldes; geladen, sobald der
  // Versionen-Tab offen ist (und neu nach jeder gespeicherten Änderung).
  const [versions, setVersions] = React.useState<DraftVersionSummaryDto[] | null>(null)
  const [versionsError, setVersionsError] = React.useState<string | null>(null)
  const [restoringId, setRestoringId] = React.useState<string | null>(null)
  const [versionNotice, setVersionNotice] = React.useState<string | null>(null)
  const selectedIdRef = React.useRef<string | null>(null)
  const autoSelectedRef = React.useRef(false)
  const editorRef = React.useRef<RichTextEditorHandle>(null)

  const selected = fields?.find((f) => f.field_id === selectedId) ?? null
  const showA2Controls = isA2Field(selected?.field_id)
  const comparisonEnabled = caps?.features?.market_comparison === true
  const marketResearchEnabled = caps?.features?.web_research === true

  React.useEffect(() => {
    // Wie auf der Quellen-Seite: kurz nachpollen, solange ein abgelaufener
    // Live-Preflight sich im Backend selbst erneuert (max. ~60 s).
    let active = true
    let attempts = 0
    let timer: ReturnType<typeof setTimeout> | undefined
    const load = async () => {
      const c = await getCapabilities()
      if (!active) return
      setCaps(c)
      if (capabilitiesSelfHealing(c) && attempts < 12) {
        attempts += 1
        timer = setTimeout(() => void load(), 5000)
      }
    }
    void load()
    return () => {
      active = false
      if (timer) clearTimeout(timer)
    }
  }, [])

  React.useEffect(() => {
    if (!comparisonEnabled || !marketProjectId) return
    let active = true
    getLatestComparison(marketProjectId)
      .then((c) => {
        if (active) setComparison(c)
      })
      .catch(() => undefined)
      .finally(() => {
        if (active) setComparisonLoaded(true)
      })
    return () => {
      active = false
    }
  }, [comparisonEnabled, marketProjectId])

  // §10 Quellen-Redraft: mindestens eine live abgerufene, importierte und
  // inhaltlich positiv geprüfte Quelle vorhanden? (Spiegelt den Backend-Filter
  // retrieve_advisory_research_context — das Backend bleibt autoritativ.)
  const [reviewedSourcesReady, setReviewedSourcesReady] = React.useState(false)
  React.useEffect(() => {
    if (!marketResearchEnabled || !marketProjectId) return
    let active = true
    getResearchWorkspace(marketProjectId)
      .then((ws) => {
        if (!active) return
        setReviewedSourcesReady(
          ws.results.some(
            (r) =>
              r.status === "imported" &&
              r.content_review_status === "reviewed" &&
              (r.support_status === "supports" ||
                r.support_status === "partially_supports") &&
              r.execution_mode !== "fake_demo"
          )
        )
      })
      .catch(() => undefined)
    return () => {
      active = false
    }
  }, [marketResearchEnabled, marketProjectId])

  function resetA2() {
    setA2Suggestion(null)
    setA2Loading(false)
    setA2UnavailableReason(null)
    setA2Error(null)
    setA2RetryAlternative(false)
    setA2ReviewOpen(false)
    setA2Accepting(false)
    setA2FromRun(false)
    setA2ContextOptions(null)
    setA2SelectedAnchors(new Set())
    setA2AnchorsOpen(false)
  }

  // Im Analyse-Lauf erzeugte Vorschläge (proposed, zur aktuellen Basis)
  // beim Feldwechsel anzeigen — Anzeige only, nie Auto-Übernahme.
  async function loadRunSuggestion(
    draft: PortalFieldDraftDto,
    targetSection?: string
  ) {
    if (!isA2Field(draft.field_id)) return
    try {
      const suggestion = await getRunFieldSuggestion(
        runId,
        draft.field_id,
        targetSection
      )
      if (
        suggestion &&
        suggestion.base_version_id === draft.current_version.draft_version_id &&
        selectedIdRef.current === draft.field_id
      ) {
        setA2Suggestion(suggestion)
        setA2FromRun(true)
      }
    } catch {
      // Read-only-Zusatz: ein Fehler blockiert den Editor nie.
    }
  }

  const loadReview = React.useCallback(() => {
    getReview(runId)
      .then(setReview)
      .catch(() => setReview(null))
  }, [runId])

  const load = React.useCallback(() => {
    setLoadError(null)
    setFields(null)
    Promise.all([
      listFields(runId),
      listEvidence(runId).catch(() => []),
      listPortalFields(runId).catch(() => []),
    ])
      .then(([drafts, ev, catalog]) => {
        setFields(drafts)
        setAnchors(ev)
        setPortalCatalog(catalog)
        if (drafts.length && !autoSelectedRef.current) {
          autoSelectedRef.current = true
          // Deep link (?field=…) wins over the default first field; unknown
          // ids fall back silently to the first field.
          const preferred = initialFieldId
            ? drafts.find((d) => d.field_id === initialFieldId)
            : undefined
          selectField(preferred ?? drafts[0], catalog)
          if (preferred) {
            requestAnimationFrame(() => editorRef.current?.focus())
          }
        }
      })
      .catch((e) =>
        setLoadError(e instanceof Error ? e.message : "Entwürfe konnten nicht geladen werden.")
      )
    // Requirements feed the per-field "Betroffene Anforderungen" join; a
    // failure degrades to the empty state instead of blocking the editor.
    listRequirements(runId)
      .then(setRequirements)
      .catch(() => setRequirements([]))
    loadReview()
  }, [runId, loadReview, initialFieldId])

  React.useEffect(() => load(), [load])

  function selectField(
    draft: PortalFieldDraftDto,
    catalog: PortalFieldInfoDto[] = portalCatalog
  ) {
    const target =
      catalog.find((p) => p.field_id === draft.field_id)?.subsections?.[0]?.marker ??
      null
    setSelectedId(draft.field_id)
    selectedIdRef.current = draft.field_id
    setLocalText(draft.current_version.text)
    setBaseVersionId(draft.current_version.draft_version_id)
    setSaveState("saved")
    setErrorMsg(null)
    setRecheck(null)
    setFieldNotice(null)
    setNotesNotice(null)
    setConfirmResolveId(null)
    setAssistantTab(null)
    setSelectedSubsection(target)
    resetA2()
    void loadRunSuggestion(draft, target ?? undefined)
  }

  // Fokusansicht (B1): Abschnitt auswählen — der Editor zeigt danach nur noch
  // dessen Antwortbereich, ein Sprung im Volltext ist nicht nötig.
  function focusSubsection(marker: string) {
    setSelectedSubsection(marker)
    resetA2()
    if (selected) void loadRunSuggestion(selected, marker)
  }

  // Fallback (Degraded-Modus ohne parsebare Marker): Sprung zur Markerstelle
  // im Ein-Block-Editor.
  function selectSubsection(marker: string) {
    setSelectedSubsection(marker)
    editorRef.current?.selectMatch(marker)
    resetA2()
    if (selected) void loadRunSuggestion(selected, marker)
  }

  async function generateSuggestion(
    modelPreference?: "primary" | "alternative"
  ) {
    if (!selected) return
    setA2Loading(true)
    setA2Error(null)
    setA2ErrorRetryable(true)
    setA2RetryAlternative(false)
    setA2UnavailableReason(null)
    try {
      const suggestion = await createRedraft(
        runId,
        selected.field_id,
        baseVersionId,
        undefined,
        selectedSubsection ?? undefined,
        modelPreference,
        {
          improvementMode: a2ImprovementMode,
          selectedAnchorIds: [...a2SelectedAnchors],
        }
      )
      // Ein frisch erzeugter Live-Vorschlag stammt nie aus dem Analyse-Lauf —
      // sonst bliebe das Herkunfts-Banner der Analyse fälschlich stehen.
      setA2FromRun(false)
      setA2Suggestion(suggestion)
      setA2ReviewOpen(true)
    } catch (e) {
      if (e instanceof RedraftError && e.status === 503) {
        // Ohne bekannten Code fail-closed auf provider_unavailable.
        setA2UnavailableReason(e.reasonCode ?? FALLBACK_AI_REASON)
      } else if (e instanceof RedraftError && e.status === 409) {
        setConflict(true)
      } else if (e instanceof RedraftError && e.reasonCode) {
        // Auch ein Operation-Fehler mit Blockgrund (z. B. Live-Preflight)
        // zeigt Grund + CTA — nie einen Demo-Ersatz.
        setA2UnavailableReason(e.reasonCode)
      } else {
        setA2Error(e instanceof Error ? e.message : "Vorschlag fehlgeschlagen.")
        // Deterministische Abschnittsfehler: Wiederholen kann nie gelingen.
        if (e instanceof RedraftError && isDeterministicRedraftFailure(e.code)) {
          setA2ErrorRetryable(false)
        }
        // Nur transiente Providerfehler bieten die Alternativroute an.
        if (e instanceof RedraftError && e.retryWithAlternativeModel) {
          setA2RetryAlternative(true)
        }
      }
    } finally {
      setA2Loading(false)
    }
  }

  // C3 — `textOverride` trägt die Teilübernahme (gemergter Abschnittstext aus
  // den gewählten Änderungen); ohne Override wird der ganze Vorschlag exakt
  // übernommen. Beide Wege laufen über denselben PATCH mit
  // source_operation_id — das Backend merged die Ziel-Section und vergibt die
  // ehrliche Herkunft (exakt ⇒ agent, editiert ⇒ user).
  async function acceptSuggestion(textOverride?: string) {
    if (!selected || !a2Suggestion) return
    setA2Accepting(true)
    setErrorMsg(null)
    try {
      if (
        a2Suggestion.accept_mode === "whole_suggestion_only" &&
        textOverride === undefined
      ) {
        const accepted = await acceptFieldSuggestion(
          runId,
          selected.field_id,
          a2Suggestion.suggestion_id,
          a2Suggestion.base_version_id
        )
        // RUN 4B §7 — Replay ist idempotent: der Server meldet ehrlich, dass
        // KEINE zweite Version entstanden ist.
        setNotesNotice(
          accepted.idempotent_replay
            ? "Bereits übernommen — es wurde keine neue Version erstellt."
            : null
        )
        const updated = await getField(runId, selected.field_id)
        applyDraft(updated)
        setBaseVersionId(updated.current_version.draft_version_id)
        setLocalText(updated.current_version.text)
        setSaveState("saved")
        setRecheck("accepted")
        loadReview()
        resetA2()
        return
      }
      const updated = await updateField(
        runId,
        selected.field_id,
        a2Suggestion.base_version_id,
        textOverride ?? a2Suggestion.suggested_text,
        a2Suggestion.operation_id
      )
      applyDraft(updated)
      setBaseVersionId(updated.current_version.draft_version_id)
      setLocalText(updated.current_version.text)
      setSaveState("saved")
      setRecheck("accepted")
      loadReview()
      resetA2()
    } catch (e) {
      setA2Accepting(false)
      if (e instanceof FieldError && e.status === 409) {
        setA2ReviewOpen(false)
        setConflict(true)
      } else {
        // Abschnittsstruktur-Fehler beim Übernehmen tragen denselben Klartext
        // wie beim Erzeugen (Marker benannt statt Generik).
        const sectionMessage =
          e instanceof FieldError && e.code.startsWith("section_")
            ? redraftFailureLabel(e.code)
            : null
        setA2Error(
          sectionMessage ??
            (e instanceof FieldError ? e.message : "Übernehmen fehlgeschlagen.")
        )
      }
    }
  }

  async function loadSuggestionContextOptions() {
    if (!selected) return
    setA2ContextLoading(true)
    try {
      setA2ContextOptions(
        await getSuggestionContextOptions(runId, selected.field_id)
      )
    } catch (error) {
      setA2Error(error instanceof Error ? error.message : "Belege konnten nicht geladen werden.")
    } finally {
      setA2ContextLoading(false)
    }
  }

  // C3 — «Eigene Bearbeitung öffnen»: Sheet schliessen OHNE Ablehnung, den
  // Zielabschnitt fokussieren; der Vorschlag bleibt über «Vorschlag prüfen»
  // erreichbar.
  function editSuggestionTarget() {
    setA2ReviewOpen(false)
    const target = a2Suggestion?.target_section
    if (target && target !== selectedSubsection) setSelectedSubsection(target)
    editorRef.current?.focus()
  }

  // C4 — Ablehnen ist eine ausdrückliche, serverseitig persistierte
  // Entscheidung (HumanDecision auf die Suggestion; Audit ohne Rohtext).
  // Fehler beim Persistieren blenden den Vorschlag trotzdem aus — die
  // Entscheidung des Nutzers gilt; der Fehler wird angezeigt.
  async function dismissSuggestion(reason?: string) {
    const suggestionId = a2Suggestion?.suggestion_id
    setA2ReviewOpen(false)
    resetA2()
    if (!suggestionId) return
    try {
      await createHumanDecision(runId, {
        target_type: "draft_suggestion",
        target_id: suggestionId,
        action: "reject",
        comment: reason?.trim() ? reason.trim() : undefined,
      })
    } catch (e) {
      setErrorMsg(
        e instanceof Error ? e.message : "Ablehnung konnte nicht gespeichert werden."
      )
    }
  }

  function applyDraft(updated: PortalFieldDraftDto) {
    setFields((prev) => (prev ?? []).map((f) => (f.field_id === updated.field_id ? updated : f)))
  }

  // RUN 4B §9 — Historie laden, wenn der Versionen-Tab offen ist; baseVersionId
  // in den Deps hält die Liste nach Speichern/Übernahme/Restore aktuell.
  React.useEffect(() => {
    if (assistantTab !== "versionen" || !selectedId) return
    let active = true
    setVersionsError(null)
    listFieldVersions(runId, selectedId)
      .then((list) => {
        if (active) setVersions(list)
      })
      .catch(() => {
        if (active)
          setVersionsError("Die Versionshistorie konnte nicht geladen werden.")
      })
    return () => {
      active = false
    }
  }, [assistantTab, selectedId, baseVersionId, runId])

  // RUN 4B §9 — Wiederherstellen ist client-orchestriert über den bestehenden
  // Versionspfad: Alttext lesen → regulärer PATCH (neue user-Version). Der
  // Server ist autoritativ: identischer Text erzeugt KEINE redundante Version.
  async function restoreVersion(versionId: string) {
    if (!selected) return
    setRestoringId(versionId)
    setVersionNotice(null)
    setErrorMsg(null)
    try {
      const old = await getFieldVersion(runId, selected.field_id, versionId)
      const previousCurrent = selected.current_version.draft_version_id
      const updated = await updateField(
        runId,
        selected.field_id,
        previousCurrent,
        old.text
      )
      const unchanged =
        updated.current_version.draft_version_id === previousCurrent
      applyDraft(updated)
      setBaseVersionId(updated.current_version.draft_version_id)
      setLocalText(updated.current_version.text)
      setSaveState("saved")
      if (unchanged) {
        setVersionNotice("Diese Version entspricht bereits dem aktuellen Text.")
      } else {
        setVersionNotice(
          "Frühere Version wiederhergestellt und als neue Version gespeichert."
        )
        setRecheck("saved")
        loadReview()
      }
    } catch (e) {
      if (e instanceof FieldError && e.status === 409) {
        setConflict(true)
      } else {
        setErrorMsg(
          e instanceof FieldError ? e.message : "Wiederherstellen fehlgeschlagen."
        )
      }
    } finally {
      setRestoringId(null)
    }
  }

  async function refreshSelected(replaceText: boolean) {
    if (!selected) return
    const fresh = await getField(runId, selected.field_id)
    applyDraft(fresh)
    setBaseVersionId(fresh.current_version.draft_version_id)
    if (replaceText) setLocalText(fresh.current_version.text)
    setConflict(false)
    setSaveState(replaceText ? "saved" : "dirty")
  }

  async function save() {
    if (!selected) return
    setSaveState("saving")
    setErrorMsg(null)
    try {
      const updated = await updateField(runId, selected.field_id, baseVersionId, localText)
      applyDraft(updated)
      setBaseVersionId(updated.current_version.draft_version_id)
      setLocalText(updated.current_version.text)
      setSaveState("saved")
      setRecheck("saved")
      loadReview()
    } catch (e) {
      if (e instanceof FieldError && e.status === 409) {
        setConflict(true)
        setSaveState("dirty")
      } else {
        setSaveState("error")
        setErrorMsg(e instanceof FieldError ? e.message : "Speichern fehlgeschlagen.")
      }
    }
  }

  async function linkAnchor(anchorId: string) {
    if (!selected) return
    try {
      await createEvidenceLink(runId, selected.field_id, anchorId, baseVersionId)
      await refreshSelected(false)
      setRecheck("saved")
    } catch (e) {
      setErrorMsg(e instanceof FieldError ? e.message : "Verknüpfung fehlgeschlagen.")
    }
  }

  async function unlink(linkId: string) {
    if (!selected) return
    try {
      await deleteEvidenceLink(runId, selected.field_id, linkId)
      await refreshSelected(false)
      loadReview()
    } catch {
      /* ignore */
    }
  }

  async function addComment() {
    if (!selected || !commentText.trim()) return
    try {
      await createHumanDecision(runId, {
        target_type: "portal_field_draft",
        target_id: selected.draft_id,
        action: "request_changes",
        // The chosen type is stored as a visible prefix in the comment text
        // ("[Frage] …") — the contract has no comment-type field.
        comment: commentWithType(commentType, commentText.trim()),
      })
      setCommentText("")
      setCommentType("Hinweis")
      loadReview()
    } catch (e) {
      setErrorMsg(e instanceof Error ? e.message : "Kommentar fehlgeschlagen.")
    }
  }

  // B5 — Arbeitsnotizen: markierten Text aus dem Antragstext entfernen und als
  // Notiz (Kommentar-Kanal, Typ «Notiz») zum Abschnitt speichern. Der Text
  // verlässt den Entwurf über deleteSelection → onChange (dirty, nie Auto-Save).
  async function moveSelectionToNotes() {
    if (!selected) return
    const selection = editorRef.current?.getSelectedText().trim() ?? ""
    if (!selection) {
      setNotesNotice(
        "Bitte zuerst den Text markieren, der in die Notizen verschoben werden soll."
      )
      return
    }
    setNotesNotice(null)
    try {
      await createHumanDecision(runId, {
        target_type: "portal_field_draft",
        target_id: selected.draft_id,
        action: "request_changes",
        comment: commentWithType("Notiz", selection),
      })
      editorRef.current?.deleteSelection()
      setNotesNotice(
        "In die Notizen verschoben — der Text wurde aus dem Antragstext entfernt (noch nicht gespeichert)."
      )
      loadReview()
    } catch (e) {
      setErrorMsg(e instanceof Error ? e.message : "Notiz fehlgeschlagen.")
    }
  }

  /**
   * "Als Argument übernehmen" — inserts an allowed, source-qualified formulation
   * as a new paragraph at the editor cursor (via the editor handle). The editor's
   * onChange then updates the local buffer + dirty state (audited/versioned/undo);
   * never auto-saves and never bypasses that path.
   */
  function insertMarketText(text: string) {
    editorRef.current?.insertTextAtCursor(text)
  }

  /** Contextual shortcut per review hint: placeholder → mark it; evidence → open Belege. */
  function findingAction(
    f: ReviewFindingDto
  ): { label: string; onClick: () => void } | null {
    const text = f.description.toLowerCase()
    if (/platzhalter|\[\[|\btbd\b|\btodo\b|angabe ergänzen/.test(text)) {
      return {
        label: "Zum Platzhalter",
        onClick: () => editorRef.current?.selectPlaceholder(0),
      }
    }
    if (/beleg|evidenz|fundstelle|quelle/.test(text)) {
      return { label: "Quellen öffnen", onClick: () => setAssistantTab("quellen") }
    }
    return null
  }

  async function resolveFinding(findingId: string) {
    try {
      await createHumanDecision(runId, {
        target_type: "review_finding",
        target_id: findingId,
        action: "dismiss",
      })
      loadReview()
    } catch {
      /* ignore */
    }
  }

  async function approveField() {
    if (!selected || !review) return
    setFieldNotice(null)
    setErrorMsg(null)
    try {
      await createApproval(runId, review, "field", selected.field_id)
      setFieldNotice("Abschnitt freigegeben.")
      loadReview()
    } catch (e) {
      setErrorMsg(e instanceof ReviewError ? e.message : "Freigabe fehlgeschlagen.")
    }
  }

  const selectedFindings: ReviewFindingDto[] = (review?.findings ?? []).filter(
    (f) => f.field_id === selected?.field_id
  )
  const fieldApprovable =
    !!review &&
    !review.recheck_required &&
    !selectedFindings.some((f) => f.severity === "blocker")

  if (loadError) {
    return (
      <div className="py-10 text-center">
        <p className="text-sm text-muted-foreground">{loadError}</p>
        <Button variant="outline" className="mt-4" onClick={load}>
          <RefreshCw data-icon="inline-start" />
          Erneut versuchen
        </Button>
      </div>
    )
  }
  if (fields === null) {
    return (
      <div className="grid gap-4 lg:grid-cols-[320px_1fr_360px]">
        <Skeleton className="h-72 w-full" />
        <Skeleton className="h-72 w-full" />
        <Skeleton className="h-72 w-full" />
      </div>
    )
  }
  if (fields.length === 0 || !selected) {
    return (
      <p className="py-10 text-center text-sm text-muted-foreground">
        Für diesen Lauf liegen noch keine Feldentwürfe vor.
      </p>
    )
  }

  const limit = selected.character_limit ?? null
  const count = charCount(localText)
  const overLimit = limit != null && count > limit
  const draftLinks = selected.evidence_links
  const hasStaleLink = draftLinks.some((l) => l.status === "stale")
  const linkedAnchorIds = new Set(
    draftLinks.filter((l) => l.status === "active").map((l) => l.anchor_id)
  )
  const anchorById = new Map(anchors.map((a) => [a.anchor_id, a]))
  const visibleLinks = draftLinks.filter((l) => l.status !== "removed")

  // Requirements ↔ field join (Slice 4): primary over the registry-declared
  // affected_field_ids; the findings-based join stays as a union fallback for
  // findings whose requirement does not declare the field.
  const fieldRequirementIds = new Set(
    selectedFindings
      .map((f) => f.requirement_id)
      .filter((id): id is string => Boolean(id))
  )
  const fieldRequirements = (requirements ?? []).filter(
    (r) =>
      (selected && r.affected_field_ids?.includes(selected.field_id)) ||
      fieldRequirementIds.has(r.requirement_id)
  )

  const viewModels = fields.map((f) => liveFieldToViewModel(f, review))
  const activeVm = viewModels.find((v) => v.id === selected.field_id) ?? viewModels[0]

  // R6: sichtbare Unterabschnitte des ausgewählten Composite-Felds (Registry).
  const subsectionDefs =
    portalCatalog.find((p) => p.field_id === selected.field_id)?.subsections ?? []
  // Parse-Zustand des AKTUELLEN Texts (2026-07-24): Marker, deren Zeile im
  // Text fehlt, sind nicht wählbar — das Backend braucht nur den Zielmarker,
  // alle übrigen dürfen fehlen (ziel-tolerante Abschnittsbearbeitung).
  const subsectionOutline = buildOutline(localText, subsectionDefs)
  const targetMarkerMissing = Boolean(
    selectedSubsection &&
      subsectionOutline.some(
        (entry) => entry.marker === selectedSubsection && entry.index < 0
      )
  )
  const configuredGenerationKind: GenerationKind | null =
    caps?.generation_mode === "fake_demo"
      ? "fake_demo"
      : caps?.generation_mode === "real_eval"
        ? "model_generated"
        : null
  // Ohne konfigurierten Provider ist die Aktion deaktiviert und der konkrete
  // Grund (aus den Capabilities) steht direkt darunter. caps === null
  // (Laderennen) blockiert bewusst nicht — der Klick scheitert dann sicher
  // über den 503-Reason-Pfad.
  const capsBlockedReason =
    caps && configuredGenerationKind === null
      ? (caps.generation_unavailable_reason ??
        caps.ai_unavailable_reason ??
        FALLBACK_AI_REASON)
      : null
  const visibleGenerationKind =
    a2Suggestion?.generation_kind ?? configuredGenerationKind
  const currentReviewText =
    selectedSubsection && subsectionDefs.length > 0
      ? (subsectionText(localText, subsectionDefs, selectedSubsection) ?? localText)
      : localText
  // Erst-Entwurf: Zieltext ist leer oder nur Vorlagen-Platzhalter — Spiegel
  // der Backend-Erkennung (assemble_a2_context / _section_is_initial_draft).
  const selectedSubsectionContent =
    selectedSubsection && subsectionDefs.length > 0
      ? subsectionContent(localText, subsectionDefs, selectedSubsection)
      : null
  const isInitialDraft =
    selectedSubsection && subsectionDefs.length > 0
      ? selectedSubsectionContent !== null &&
        isPlaceholderOnly(selectedSubsectionContent)
      : isPlaceholderOnly(localText)
  // Beim Erst-Entwurf beschreibt die Aktion das Ergebnis; das ehrliche
  // Demo-Label («Demo-Vorschlag erstellen») bleibt unverändert.
  const suggestionAction =
    isInitialDraft && configuredGenerationKind === "model_generated"
      ? "Erst-Entwurf erstellen"
      : generationActionLabel(configuredGenerationKind)

  const hasBlocker = (review?.blocker_count ?? 0) > 0 || selectedFindings.some((f) => f.severity === "blocker")
  const hasBackedMarketData =
    comparisonEnabled &&
    (comparison?.items.some((i) => i.confidence_label === "source_backed") ?? false)
  const defaultTab = pickDefaultTab(activeVm, {
    hasMarketData: hasBackedMarketData,
    hasFindings: selectedFindings.length > 0,
    hasBlocker,
  })

  // --- Right panel: Belege (live evidence cards + linking) ---
  const belegeContent = (
    <div className="flex flex-col gap-3">
      <div className="text-xs text-muted-foreground">
        <p>{LINK_EXPLANATION}</p>
        <details className="mt-1">
          <summary className="cursor-pointer">Wofür zählt eine Verknüpfung?</summary>
          <p className="mt-1">{LINK_EXPLANATION_DETAILS}</p>
        </details>
      </div>
      {hasStaleLink && (
        <p className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-900">
          {STALE_LINK_NOTICE}
        </p>
      )}
      {visibleLinks.length === 0 ? (
        <p className="text-xs text-muted-foreground">
          Noch keine Belege mit diesem Feld verknüpft.
        </p>
      ) : (
        <ul className="flex flex-col gap-2">
          {visibleLinks.map((l) => {
            const anchor = anchorById.get(l.anchor_id)
            const claim = l.claim_text?.trim() || anchor?.quote || "Aussage nicht verfügbar"
            const isUrl = anchor?.source_type === "url"
            return (
              <li
                key={l.evidence_link_id}
                className="flex flex-col gap-1.5 rounded-md border border-border px-3 py-2"
              >
                <p className="text-xs leading-relaxed text-foreground">{claim}</p>
                <p className="text-[11px] text-muted-foreground">
                  {anchor ? (
                    <>
                      {anchor.source_name}
                      <span className="ml-1.5 rounded bg-muted px-1 py-0.5">
                        {EVIDENCE_SOURCE_TYPE_LABELS[anchor.source_type]}
                      </span>
                      {" · "}
                      {formatFundstelle(anchor)}
                    </>
                  ) : (
                    "Quelle nicht mehr verfügbar"
                  )}
                </p>
                <div className="flex flex-wrap items-center gap-1.5">
                  {/* Bewusst das lange Label: die verknüpfte Belegliste ist die
                      Primärfläche und muss den Vorbehalt («fachliche Prüfung
                      offen») mittragen. Die Auswahlliste unten ist sekundär und
                      nutzt die Kurzform. */}
                  {anchor && (
                    <SupportStatusBadge
                      status={
                        l.support_status ??
                        anchor.support_status ??
                        supportStatusFromVerification(anchor.verification_status)
                      }
                    />
                  )}
                  {l.status === "stale" && (
                    <Badge variant="outline">{EVIDENCE_LINK_STATUS_LABELS.stale}</Badge>
                  )}
                </div>
                <div className="flex flex-wrap items-center gap-3">
                  {anchor && (
                    <a
                      href={
                        isUrl
                          ? anchor.source_name
                          : `/anforderungen?tab=evidenz&anchor=${encodeURIComponent(anchor.anchor_id)}`
                      }
                      {...(isUrl ? { target: "_blank", rel: "noopener noreferrer" } : {})}
                      className="inline-flex items-center gap-1 text-[11px] font-medium text-muted-foreground hover:text-foreground"
                    >
                      <ExternalLink className="size-3" />
                      Quelle öffnen
                    </a>
                  )}
                  <button
                    type="button"
                    onClick={() => unlink(l.evidence_link_id)}
                    className="inline-flex items-center gap-1 text-[11px] font-medium text-muted-foreground hover:text-destructive"
                  >
                    <Trash2 className="size-3" />
                    Verknüpfung entfernen
                  </button>
                </div>
              </li>
            )
          })}
        </ul>
      )}

      <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        Weitere Belege verknüpfen
      </h4>
      {anchors.length === 0 ? (
        <p className="text-xs text-muted-foreground">
          Für diesen Lauf liegen noch keine Belege vor.{" "}
          <a href="/quellen" className="font-medium text-primary hover:underline">
            Quellen öffnen
          </a>
        </p>
      ) : (
        (showAllAnchors ? anchors : anchors.slice(0, ANCHOR_PREVIEW_COUNT)).map((a) => (
          <div key={a.anchor_id} className="rounded border border-border px-2 py-2 text-xs">
            <div className="flex items-center justify-between gap-2">
              <span className="truncate text-muted-foreground">{a.source_name}</span>
              <SupportStatusBadge
                short
                status={
                  a.support_status ??
                  supportStatusFromVerification(a.verification_status)
                }
              />
            </div>
            <p className="mt-1 line-clamp-2">{a.quote}</p>
            <Button
              variant="ghost"
              size="xs"
              className="mt-1"
              disabled={linkedAnchorIds.has(a.anchor_id)}
              onClick={() => linkAnchor(a.anchor_id)}
            >
              <Link2 className="mr-1 size-3" />
              {linkedAnchorIds.has(a.anchor_id) ? "Verknüpft" : "Verknüpfen"}
            </Button>
          </div>
        ))
      )}
      {!showAllAnchors && anchors.length > ANCHOR_PREVIEW_COUNT && (
        <Button
          variant="ghost"
          size="xs"
          className="self-start"
          onClick={() => setShowAllAnchors(true)}
        >
          {`Alle ${anchors.length} Belege anzeigen`}
        </Button>
      )}
    </div>
  )

  // --- Right panel: Fehlende Angaben (konkrete Fragen: Platzhalter +
  // Anforderungen mit fehlenden Angaben + betroffene Anforderungen) ---
  const openPlaceholders = placeholderMatches(localText)
  const needsInputRequirements = fieldRequirements.filter(
    (r) => r.status === "needs_input"
  )
  const fehlendeQuestions = (
    <>
      {openPlaceholders.length > 0 && (
        <div className="flex flex-col gap-1.5">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Offene Angaben im Text
          </h4>
          <ul className="flex flex-col gap-1">
            {openPlaceholders.map((m, i) => {
              const snippet = localText.slice(m.start, m.end)
              return (
                <li
                  key={`${m.start}-${m.end}`}
                  className="flex items-start justify-between gap-2 rounded border border-border px-2 py-1.5 text-xs"
                >
                  <span className="min-w-0 flex-1 text-foreground">
                    Welche Angabe gehört hier hin? „{snippet}“
                  </span>
                  <button
                    type="button"
                    onClick={() => editorRef.current?.selectPlaceholder(i)}
                    className="shrink-0 text-[11px] font-medium text-primary hover:underline"
                  >
                    Im Text markieren
                  </button>
                </li>
              )
            })}
          </ul>
        </div>
      )}
      {needsInputRequirements.length > 0 && (
        <div className="flex flex-col gap-1.5">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Fehlende Angaben zu Anforderungen
          </h4>
          <ul className="flex flex-col gap-1">
            {needsInputRequirements.map((r) => (
              <li
                key={r.assessment_id}
                className="rounded border border-border px-2 py-1.5 text-xs text-foreground"
              >
                {`Welche Angaben fehlen zu „${r.title?.trim() || REQ_FALLBACK.title}“?`}{" "}
                <a
                  href={`/anforderungen?requirement=${encodeURIComponent(r.requirement_id)}`}
                  className="font-medium text-primary hover:underline"
                >
                  Angaben ergänzen
                </a>
              </li>
            ))}
          </ul>
        </div>
      )}
    </>
  )

  // --- Right panel: betroffene Anforderungen (Teil von "Fehlende Angaben") ---
  const anforderungenContent =
    requirements === null ? (
      <Skeleton className="h-16 w-full" />
    ) : fieldRequirements.length === 0 ? (
      <div className="flex flex-col gap-2">
        <p className="text-xs text-muted-foreground">
          Keine Anforderungen mit diesem Feld verknüpft. Dieses Feld kann trotzdem
          für die Fördervoraussetzungen relevant sein.
        </p>
        <Button
          variant="outline"
          size="sm"
          className="self-start"
          render={<a href="/anforderungen" />}
          nativeButton={false}
        >
          Anforderungen prüfen
        </Button>
      </div>
    ) : (
      <ul className="flex flex-col gap-2">
        {fieldRequirements.map((r) => {
          const bucket = liveStatusToBucket(r.status)
          const hasEvidence = r.evidence_links.length > 0
          const humanNeeded = r.basis !== "human_override" && bucket !== "fulfilled"
          return (
            <li
              key={r.assessment_id}
              className="flex flex-col gap-1.5 rounded-md border border-border px-3 py-2"
            >
              <div className="flex items-start justify-between gap-2">
                <span className="min-w-0 flex-1 text-xs font-medium text-foreground">
                  {r.title?.trim() || REQ_FALLBACK.title}
                </span>
                <ReqBucketBadge bucket={bucket} />
              </div>
              <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-[11px] text-muted-foreground">
                <span>
                  {hasEvidence ? EVIDENCE_STATE_LABELS.present : EVIDENCE_STATE_LABELS.missing}
                </span>
                {humanNeeded && <span>{HUMAN_STATE_LABELS.needed}</span>}
                {r.stale && <span className="text-status-partial">Prüfung veraltet</span>}
              </div>
              <a
                href={`/anforderungen?requirement=${encodeURIComponent(r.requirement_id)}`}
                className="text-[11px] font-medium text-primary hover:underline"
              >
                In Anforderungen öffnen
              </a>
            </li>
          )
        })}
      </ul>
    )

  const fehlendeContent = (
    <div className="flex flex-col gap-3">
      {openPlaceholders.length === 0 && needsInputRequirements.length === 0 && (
        <p className="text-xs text-muted-foreground">
          Keine offenen Angaben im Text dieses Abschnitts.
        </p>
      )}
      {fehlendeQuestions}
      <div className="flex flex-col gap-1.5">
        <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Betroffene Anforderungen
        </h4>
        {anforderungenContent}
      </div>
    </div>
  )

  // --- Right panel: Schwächen (feldbezogene Findings mit Warum/Aktion/HITL) ---
  const schwaechenContent = (
    <div className="flex flex-col gap-2">
      {selectedFindings.length === 0 ? (
        <p className="text-xs text-muted-foreground">
          Für diesen Abschnitt liegen keine Schwächen-Hinweise vor.
        </p>
      ) : (
        <ul className="flex flex-col gap-2">
          {selectedFindings.map((f) => {
            const action = findingAction(f)
            return (
              <li
                key={f.finding_id}
                className="flex flex-col gap-1.5 rounded-md border border-border px-3 py-2 text-xs"
              >
                <div className="flex items-start gap-2">
                  <Badge
                    variant={f.severity === "blocker" ? "destructive" : "outline"}
                    className="shrink-0"
                  >
                    {f.severity === "blocker" ? "Blocker" : "Hinweis"}
                  </Badge>
                  {isAiFinding(f) && (
                    <Badge variant="outline" className="shrink-0">
                      KI-Prüfung
                    </Badge>
                  )}
                </div>
                {/* Warum */}
                <p className="text-foreground">{parseCommentType(f.description).text}</p>
                {/* Nächste Aktion */}
                {f.suggested_improvement && (
                  <p className="text-muted-foreground">
                    Nächster Schritt: {f.suggested_improvement}
                  </p>
                )}
                {action && (
                  <button
                    type="button"
                    onClick={action.onClick}
                    className="self-start text-[11px] font-medium text-primary hover:underline"
                  >
                    {action.label}
                  </button>
                )}
              </li>
            )
          })}
        </ul>
      )}
      {/* HITL-Hinweis: die fachliche Entscheidung bleibt beim Menschen. */}
      <p className="text-[11px] text-muted-foreground">
        Hinweise sind Unterstützung für Ihre Prüfung — sie sind keine
        Förderentscheidung.{" "}
        <a href="/review" className="font-medium text-primary hover:underline">
          Zur Gesamtprüfung
        </a>
      </p>
    </div>
  )

  // --- Right panel: Kommentare (review hints + comment box + approve) ---
  const kommentareContent = (
    <div className="flex flex-col gap-3">
      <section className="flex flex-col gap-2">
        <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Review-Hinweise
        </h4>
        {selectedFindings.length === 0 ? (
          <p className="text-xs text-muted-foreground">
            Keine offenen Hinweise für diesen Abschnitt.
          </p>
        ) : (
          <ul className="flex flex-col gap-1">
            {selectedFindings.map((f) => {
              const parsed = parseCommentType(f.description)
              const action = findingAction(f)
              const confirming = confirmResolveId === f.finding_id
              return (
                <li
                  key={f.finding_id}
                  className="flex flex-col gap-1.5 rounded border border-border px-2 py-1.5 text-xs"
                >
                  <div className="flex items-start justify-between gap-2">
                    <span>
                      <Badge
                        variant={f.severity === "blocker" ? "destructive" : "outline"}
                        className="mr-1 align-middle"
                      >
                        {f.severity === "blocker" ? "Blocker" : (parsed.type ?? "Hinweis")}
                      </Badge>
                      {isAiFinding(f) && (
                        <Badge variant="outline" className="mr-1 align-middle">
                          KI-Prüfung
                        </Badge>
                      )}
                      {parsed.text}
                    </span>
                    {!confirming && (
                      <Button
                        variant="ghost"
                        size="xs"
                        onClick={() => setConfirmResolveId(f.finding_id)}
                      >
                        Erledigt
                      </Button>
                    )}
                  </div>
                  {action && !confirming && (
                    <button
                      type="button"
                      onClick={action.onClick}
                      className="self-start text-[11px] font-medium text-primary hover:underline"
                    >
                      {action.label}
                    </button>
                  )}
                  {confirming && (
                    <div className="flex flex-wrap items-center gap-2 border-t border-border pt-1.5">
                      <span className="text-[11px] text-muted-foreground">
                        Als erledigt markieren? Der Hinweis wird aus der Liste entfernt.
                      </span>
                      <Button
                        variant="outline"
                        size="xs"
                        onClick={() => {
                          setConfirmResolveId(null)
                          void resolveFinding(f.finding_id)
                        }}
                      >
                        Bestätigen
                      </Button>
                      <Button
                        variant="ghost"
                        size="xs"
                        onClick={() => setConfirmResolveId(null)}
                      >
                        Abbrechen
                      </Button>
                    </div>
                  )}
                </li>
              )
            })}
          </ul>
        )}
      </section>

      <div className="flex flex-col gap-1">
        <div
          role="group"
          aria-label="Kommentar-Typ"
          className="flex flex-wrap items-center gap-1"
        >
          <span className="text-[11px] text-muted-foreground">Typ:</span>
          {COMMENT_TYPES.map((t) => (
            <button
              key={t}
              type="button"
              aria-pressed={commentType === t}
              onClick={() => setCommentType(t)}
              className={
                commentType === t
                  ? "rounded-full border border-primary/40 bg-primary/10 px-2 py-0.5 text-[11px] font-medium text-primary"
                  : "rounded-full border border-border bg-card px-2 py-0.5 text-[11px] text-muted-foreground hover:text-foreground"
              }
            >
              {t}
            </button>
          ))}
        </div>
        <Textarea
          value={commentText}
          onChange={(e) => setCommentText(e.target.value)}
          rows={2}
          aria-label="Kommentar zum Abschnitt"
          placeholder="Kommentar zum Abschnitt hinzufügen …"
          className="min-h-[96px] bg-white text-slate-950 border border-slate-200 rounded-md p-3"
        />
      </div>
      <div className="flex items-center justify-between gap-2">
        <Button size="sm" variant="outline" onClick={addComment} disabled={!commentText.trim()}>
          Kommentar hinzufügen
        </Button>
        <Button size="sm" onClick={approveField} disabled={!fieldApprovable}>
          Abschnitt freigeben
        </Button>
      </div>
      {fieldNotice && <p role="status" className="text-xs text-emerald-700">{fieldNotice}</p>}
      {!fieldApprovable && review?.recheck_required && (
        <p className="text-xs text-muted-foreground">
          Freigabe erst nach erneuter Prüfung möglich.{" "}
          <a href="/review" className="font-medium text-primary hover:underline">
            Zur Qualitätsprüfung
          </a>
        </p>
      )}
      {!fieldApprovable && review && !review.recheck_required && (
        <p className="text-xs text-muted-foreground">
          Freigabe möglich, sobald keine Blocker-Hinweise für diesen Abschnitt offen sind.
        </p>
      )}
    </div>
  )

  const conflictDialog = (
    <Dialog open={conflict} onOpenChange={setConflict}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Dieser Abschnitt wurde zwischenzeitlich geändert.</DialogTitle>
        </DialogHeader>
        <p className="text-sm text-muted-foreground">
          Ihre Eingaben bleiben erhalten. Sie können die neueste Version laden oder
          Ihren Text behalten und erneut speichern.
        </p>
        <DialogFooter>
          <Button variant="outline" onClick={() => refreshSelected(true)}>
            Neueste Version laden
          </Button>
          <Button onClick={() => refreshSelected(false)}>Eigenen Text behalten</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )

  const editorShell = (
    <DraftWorkspaceShell
      subtitle="Bearbeiten Sie die Texte pro Innolink-Feld, prüfen Sie Vorschläge, Belege und offene Punkte."
      viewModels={viewModels}
      selectedId={selected.field_id}
      onSelect={(id) => {
        const f = fields.find((x) => x.field_id === id)
        if (f) selectField(f)
      }}
      activeVm={activeVm}
      text={localText}
      onChangeText={(value) => {
        setLocalText(value)
        setSaveState("dirty")
        setRecheck(null)
      }}
      onSave={save}
      saveDisabled={saveState === "saving" || saveState === "saved" || overLimit}
      saveStateLabel={SAVE_STATE_LABEL[saveState]}
      deinTextBadge={
        <>
          {/* RUN 4B §7 — Herkunft in Nutzersprache («Aus KI-Vorschlag
              übernommen» nur bei verifizierter Provenienz); die Generierungsart
              bleibt als eigener Chip sichtbar (Live-KI vs. Demo). */}
          <Badge
            variant={selected.current_version.generation_kind ? "outline" : "secondary"}
            className={cn(
              selected.current_version.generation_kind &&
                GENERATION_KIND_BADGE_CLASS[selected.current_version.generation_kind]
            )}
          >
            {versionOriginLabel(
              selected.current_version.created_by,
              selected.current_version.generation_kind
            )}
          </Badge>
          {selected.current_version.created_by === "agent" &&
            selected.current_version.generation_kind && (
              <Badge
                variant="outline"
                className={
                  GENERATION_KIND_BADGE_CLASS[
                    selected.current_version.generation_kind
                  ]
                }
              >
                {generationLabel(selected.current_version.generation_kind)}
              </Badge>
            )}
          {/* C8 — nach einer Übernahme/Änderung: klarer Status statt nur Banner. */}
          {recheck && (
            <Badge
              variant="outline"
              className="border-status-partial/40 bg-status-partial/10 text-status-partial"
            >
              In Bearbeitung – erneute Prüfung nötig
            </Badge>
          )}
        </>
      }
      deinTextHint={
        <p className="text-xs text-muted-foreground">Bitte fachlich prüfen und ergänzen.</p>
      }
      noticeSlot={
        <>
          {recheck && (
            <p
              role="status"
              className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-900"
            >
              {recheck === "accepted" ? ACCEPT_NOTICE : RECHECK_NOTICE}
            </p>
          )}
          {notesNotice && (
            <p role="status" className="text-xs text-muted-foreground">
              {notesNotice}
            </p>
          )}
          {errorMsg && <p role="alert" className="text-xs text-destructive">{errorMsg}</p>}
        </>
      }
      deinTextActions={
        <Button
          variant="ghost"
          size="xs"
          onClick={moveSelectionToNotes}
          title="Markierten Text aus dem Antragstext entfernen und als Notiz zum Abschnitt speichern"
        >
          In Notizen verschieben
        </Button>
      }
      editorRef={editorRef}
      serverText={selected.current_version.text}
      projectId={marketProjectId}
      dataClass={workspaceDataClass}
      portalQuestion={
        portalCatalog.find((f) => f.field_id === selected.field_id)?.label
      }
      subsections={subsectionDefs}
      onJumpToSubsection={selectSubsection}
      activeSubsection={selectedSubsection}
      onSelectSubsection={focusSubsection}
      suggestionPaneLabel={
        visibleGenerationKind ? generationLabel(visibleGenerationKind) : "Vorschläge"
      }
      kiContent={
        <div className="flex flex-col gap-2">
          {showA2Controls ? (
            <div className="flex flex-col gap-2.5" data-testid="a2-suggestion-control">
              {/* Kontextzeile: Zielabschnitt und optionale Belege bleiben
                  bewusst sekundär — das Verbesserungsziel führt. */}
              <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                {subsectionDefs.length > 0 && (
                  <label className="flex items-center gap-1.5">
                    <span>Abschnitt</span>
                    <select
                      value={selectedSubsection ?? ""}
                      onChange={(event) => focusSubsection(event.target.value)}
                      className="rounded-md border border-border bg-background px-2 py-1 text-foreground"
                      aria-label="Zielabschnitt für Vorschlag"
                    >
                      {subsectionOutline.map((section) => (
                        <option
                          key={section.marker}
                          value={section.marker}
                          disabled={section.index < 0}
                        >
                          {section.index < 0
                            ? `${section.marker} — fehlt im Text`
                            : section.marker}
                        </option>
                      ))}
                    </select>
                  </label>
                )}
                <Button
                  type="button"
                  size="xs"
                  variant="ghost"
                  className="ml-auto"
                  aria-expanded={a2AnchorsOpen}
                  disabled={a2ContextLoading}
                  onClick={() => {
                    if (!a2ContextOptions && !a2ContextLoading) {
                      void loadSuggestionContextOptions()
                    }
                    setA2AnchorsOpen((open) => !open)
                  }}
                >
                  {a2ContextLoading
                    ? "Belege werden geladen …"
                    : a2SelectedAnchors.size > 0
                      ? `Belege (${a2SelectedAnchors.size})`
                      : "Belege wählen"}
                </Button>
              </div>
              {a2AnchorsOpen && a2ContextOptions && (
                <div
                  className="flex max-h-28 flex-col gap-1 overflow-y-auto rounded-md border border-border px-2 py-1.5"
                  data-testid="suggestion-anchor-options"
                >
                  {a2ContextOptions.anchors.length === 0 ? (
                    <span className="text-[11px] text-muted-foreground">Keine freigegebenen Belege verfügbar.</span>
                  ) : a2ContextOptions.anchors.map((anchor) => (
                    <label key={anchor.anchor_id} className="flex items-center gap-2 text-[11px] text-foreground">
                      <input
                        type="checkbox"
                        checked={a2SelectedAnchors.has(anchor.anchor_id)}
                        onChange={() => setA2SelectedAnchors((previous) => {
                          const next = new Set(previous)
                          if (next.has(anchor.anchor_id)) next.delete(anchor.anchor_id)
                          else next.add(anchor.anchor_id)
                          return next
                        })}
                      />
                      <span className="truncate">
                        {anchor.source_name}{anchor.section ? ` · ${anchor.section}` : ""}
                      </span>
                    </label>
                  ))}
                </div>
              )}
              {targetMarkerMissing && selectedSubsection && (
                <p role="status" className="text-xs text-muted-foreground">
                  «{selectedSubsection}» fehlt im Text — Markerzeile
                  wiederherstellen.
                </p>
              )}
              {/* Das Verbesserungsziel bestimmt das Ergebnis: eigene Fläche,
                  direkt über der Aktion, mit dem einen Erklärsatz davor. */}
              <div className="flex flex-col gap-2 rounded-lg border border-border bg-muted/20 px-3 py-2.5">
                <label className="flex flex-col gap-1">
                  <span className="text-sm font-semibold text-foreground">
                    Verbesserungsziel
                  </span>
                  <select
                    value={a2ImprovementMode}
                    onChange={(event) => setA2ImprovementMode(event.target.value as ImprovementMode)}
                    className="h-9 w-full rounded-md border border-border bg-background px-2 text-sm font-medium text-foreground"
                    aria-label="Verbesserungsziel"
                  >
                    <option value="clearer">Klarer formulieren</option>
                    <option value="complete_innolink_requirements">Fehlende Innolink-Punkte ergänzen</option>
                    <option value="shorten">Kürzen</option>
                  </select>
                </label>
                <p
                  className="text-xs text-muted-foreground"
                  data-testid="a2-action-explainer"
                >
                  {isInitialDraft
                    ? "Noch kein Text vorhanden — die KI erstellt einen Erst-Entwurf aus den sichtbaren Projektangaben und Innolink-Punkten. Nichts wird ohne Ihre Prüfung übernommen."
                    : "Der ausgewählte Abschnitt wird neu strukturiert — Fakten bleiben erhalten, nichts wird ohne Ihre Prüfung übernommen."}
                </p>
                <div className="flex flex-wrap items-center gap-2">
                  <Button
                    size="sm"
                    // Solange kein Vorschlag offen ist, ist das Erzeugen die
                    // Primäraktion; danach führt «Vorschlag prüfen».
                    variant={a2Suggestion ? "outline" : "default"}
                    onClick={() => generateSuggestion()}
                    disabled={
                      a2Loading || capsBlockedReason !== null || targetMarkerMissing
                    }
                  >
                    <Sparkles data-icon="inline-start" />
                    {a2Loading ? "Vorschlag wird erstellt …" : suggestionAction}
                  </Button>
                  {/* §10 — Redraft mit positiv geprüften Live-Quellen. Erst
                      verfügbar, wenn kein offener Vorschlag vorliegt (ein
                      offener Vorschlag würde serverseitig wiederverwendet). */}
                  {reviewedSourcesReady &&
                    !a2Suggestion &&
                    (selected.field_id === VALUE_CREATION_FIELD_ID ||
                      selected.field_id === SOLUTION_INNOVATION_FIELD_ID) && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => generateSuggestion()}
                        disabled={
                          a2Loading ||
                          capsBlockedReason !== null ||
                          targetMarkerMissing
                        }
                        data-testid="research-redraft-action"
                      >
                        Mit geprüften Quellen neu formulieren
                      </Button>
                    )}
                </div>
              </div>
              {/* RUN 4B §4/§10 — ehrlicher Pending-Zustand mit aria-live. */}
              {a2Loading && (
                <p
                  role="status"
                  aria-live="polite"
                  data-testid="a2-pending"
                  className="text-xs text-muted-foreground"
                >
                  Ihr Entwurf bleibt unverändert.
                </p>
              )}
              {a2Suggestion && !a2ReviewOpen && (
                <div
                  className="flex flex-col gap-1"
                  data-testid="a2-suggestion-summary"
                >
                  {/* Ein Prüfhinweis statt zweier: stammt der Vorschlag aus dem
                      Analyse-Lauf, trägt diese Zeile die Herkunft mit. */}
                  {a2FromRun ? (
                    <p
                      className="text-xs font-medium text-foreground"
                      data-testid="run-suggestion-hint"
                    >
                      Vorschlag aus der Analyse — Prüfung nötig.
                    </p>
                  ) : (
                    <p className="text-xs font-medium text-foreground">
                      {isInitialDraft
                        ? "Erst-Entwurf — Prüfung nötig"
                        : "Prüfung erforderlich"}
                    </p>
                  )}
                  <p className="text-xs text-muted-foreground">
                    {a2Suggestion.character_count} /{" "}
                    {a2Suggestion.character_limit} Zeichen ·{" "}
                    {(a2Suggestion.section_result?.missing_inputs ??
                      a2Suggestion.proposal?.missing_inputs ??
                      []).length}{" "}
                    offene Angaben ·{" "}
                    {(a2Suggestion.section_result?.new_claims ?? []).length}{" "}
                    unbelegte Aussagen
                  </p>
                  <div className="flex items-center gap-2">
                    {/* v2 — die EINE Primäraktion des Panels ist das Prüfen. */}
                    <Button size="sm" onClick={() => setA2ReviewOpen(true)}>
                      Vorschlag prüfen
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => void dismissSuggestion()}
                    >
                      Verwerfen
                    </Button>
                  </div>
                </div>
              )}
              {a2UnavailableReason && (
                <A2ReasonNotice reason={a2UnavailableReason} />
              )}
              {/* Ohne Provider ist die Aktion deaktiviert — mit Grund + CTA. */}
              {capsBlockedReason && !a2UnavailableReason && (
                <A2ReasonNotice reason={capsBlockedReason} />
              )}
              {configuredGenerationKind &&
                !a2Suggestion &&
                !a2Loading &&
                !a2UnavailableReason &&
                !a2Error && (
                  <p className="text-xs text-muted-foreground">
                    {generationLabel(configuredGenerationKind)} für diesen
                    Abschnitt noch nicht erstellt.
                  </p>
                )}
              {a2Error && (
                <div className="flex flex-col gap-1.5">
                  <p role="alert" className="text-xs text-destructive">
                    {a2Error}
                  </p>
                  {/* Deterministische Fehler (fehlende Markerzeile o. Ä.) sind
                      nur durch eine Textänderung behebbar — kein Retry. */}
                  {a2ErrorRetryable && (
                    <div className="flex items-center gap-2">
                      <Button
                        size="xs"
                        variant="outline"
                        onClick={() => generateSuggestion()}
                        disabled={a2Loading}
                      >
                        Erneut versuchen
                      </Button>
                      {/* Nur bei transientem Providerfehler — nie bei Policy-,
                          Budget-, Schema- oder Refusal-Fehlern. */}
                      {a2RetryAlternative && (
                        <Button
                          size="xs"
                          variant="outline"
                          onClick={() => generateSuggestion("alternative")}
                          disabled={a2Loading}
                        >
                          Mit alternativem Modell versuchen
                        </Button>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          ) : (
            <div
              className="flex flex-col gap-1.5"
              data-testid="a2-field-unavailable"
            >
              <A2ReasonNotice reason="field_not_supported" />
              <p className="text-xs text-muted-foreground">
                Verfügbar für Abstract, Executive Summary, Lösung &amp;
                Innovation, Wertschöpfung, Finanzielle Unabhängigkeit und
                Management-Stunden.
              </p>
            </div>
          )}
        </div>
      }
      assistant={
        <AssistantPanel
          key={selected.field_id}
          vm={activeVm}
          defaultTab={defaultTab}
          tab={assistantTab ?? undefined}
          onTabChange={setAssistantTab}
          market={{
            data: null,
            relevant: activeVm.isMarketRelevant,
            live: true,
            projectId: marketProjectId,
            comparison,
            comparisonLoaded,
            comparisonEnabled,
            onOpenComparison: () => setMarketSheetOpen(true),
            marketResearchEnabled,
          }}
          suggestionExists={false}
          quellenContent={belegeContent}
          fehlendeContent={fehlendeContent}
          schwaechenContent={schwaechenContent}
          kommentareContent={kommentareContent}
          versionsContent={
            <div className="flex flex-col gap-2" data-testid="version-history">
              {versionNotice && (
                <p role="status" className="text-xs text-muted-foreground">
                  {versionNotice}
                </p>
              )}
              {versionsError ? (
                <p role="alert" className="text-xs text-destructive">
                  {versionsError}
                </p>
              ) : versions === null ? (
                <p className="text-xs text-muted-foreground" aria-live="polite">
                  Versionen werden geladen …
                </p>
              ) : (
                <ul className="flex flex-col gap-1">
                  {versions.map((version) => (
                    <li
                      key={version.draft_version_id}
                      data-testid="version-row"
                      className="flex items-center justify-between gap-2 rounded-md border border-border px-3 py-2"
                    >
                      <div className="min-w-0">
                        <p className="truncate text-xs font-medium text-foreground">
                          {versionOriginLabel(
                            version.created_by,
                            version.generation_kind
                          )}
                        </p>
                        <p className="text-[11px] text-muted-foreground">
                          {new Date(version.created_at).toLocaleString("de-CH")}
                          {" · "}
                          {version.character_count} Zeichen
                        </p>
                      </div>
                      {version.is_current ? (
                        <span className="shrink-0 rounded-full bg-muted px-2 py-0.5 text-[10px] text-muted-foreground">
                          Aktuell
                        </span>
                      ) : (
                        <Button
                          variant="outline"
                          size="xs"
                          disabled={
                            restoringId !== null ||
                            saveState === "dirty" ||
                            saveState === "saving"
                          }
                          title={
                            saveState === "dirty"
                              ? "Bitte zuerst Ihre ungespeicherten Änderungen speichern oder verwerfen."
                              : undefined
                          }
                          onClick={() => void restoreVersion(version.draft_version_id)}
                        >
                          {restoringId === version.draft_version_id
                            ? "Wird wiederhergestellt …"
                            : "Wiederherstellen"}
                        </Button>
                      )}
                    </li>
                  ))}
                </ul>
              )}
              <p className="text-xs text-muted-foreground">
                Wiederherstellen speichert den früheren Text als neue Version —
                nichts geht verloren.
              </p>
            </div>
          }
        />
      }
      conflictDialog={conflictDialog}
    />
  )

  return (
    <>
      {editorShell}
      {a2Suggestion && (
        <SuggestionReviewDialog
          open={a2ReviewOpen}
          onOpenChange={(o) => {
            // Schliessen (X/ESC) ist KEIN Verwerfen — der Vorschlag bleibt
            // über «Vorschlag prüfen» erreichbar; Ablehnen ist explizit.
            if (!o) setA2ReviewOpen(false)
          }}
          currentText={currentReviewText}
          suggestion={a2Suggestion}
          onAccept={() => void acceptSuggestion()}
          onAcceptPartial={
            a2Suggestion.accept_mode === "whole_suggestion_only"
              ? undefined
              : (mergedText) => void acceptSuggestion(mergedText)
          }
          onEdit={editSuggestionTarget}
          onDismiss={(reason) => void dismissSuggestion(reason)}
          onRegenerate={() => {
            // Regenerate nutzt denselben Redraft-Pfad (idempotent, nie
            // Auto-Übernahme); das Sheet schliesst, der neue Vorschlag
            // öffnet es nach Erfolg wieder.
            setA2ReviewOpen(false)
            void generateSuggestion()
          }}
          accepting={a2Accepting}
        />
      )}
      <MarketComparisonSheet
        open={marketSheetOpen}
        onOpenChange={setMarketSheetOpen}
        comparison={comparison}
        onInsertText={insertMarketText}
      />
    </>
  )
}
