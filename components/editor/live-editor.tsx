"use client"

import * as React from "react"
import { ExternalLink, Link2, RefreshCw, Sparkles, Trash2 } from "lucide-react"
import { Button } from "@/components/ui/button"
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
  updateField,
  createEvidenceLink,
  deleteEvidenceLink,
  charCount,
  FieldError,
  type PortalFieldDraftDto,
} from "@/lib/fields"
import {
  listEvidence,
  formatFundstelle,
  VERIFICATION_LABELS,
  EVIDENCE_LINK_STATUS_LABELS,
  EVIDENCE_SOURCE_TYPE_LABELS,
  type EvidenceAnchorDto,
} from "@/lib/evidence"
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
import { getCapabilities, type Capabilities } from "@/lib/capabilities"
import {
  getLatestComparison,
  type MarketComparisonDto,
  type MarketComparisonItemDto,
} from "@/lib/market-comparison"
import { marketArgumentSentence } from "@/lib/market-view"
import { DraftWorkspaceShell } from "@/components/editor/draft-workspace-shell"
import { AssistantPanel } from "@/components/editor/assistant-panel"
import { SuggestionReviewDialog } from "@/components/editor/suggestion-review-dialog"
import { MarketComparisonSheet } from "@/components/editor/market-comparison-sheet"
import { getActiveProjectId } from "@/lib/intake-store"
import {
  CREATED_BY_LABELS,
  liveFieldToViewModel,
  pickDefaultTab,
  type AssistantTab,
} from "@/lib/draft-viewmodel"
import {
  createRedraft,
  isA2Field,
  RedraftError,
  type A2Suggestion,
} from "@/lib/redraft"

type SaveState = "saved" | "dirty" | "saving" | "error"

const RECHECK_NOTICE =
  "Änderungen gespeichert. Eine erneute Prüfung ist vor der Freigabe erforderlich."
const LINK_EXPLANATION =
  "Die Verknüpfung ordnet eine Fundstelle diesem Entwurf zu. Sie bestätigt nicht automatisch den gesamten Text."
const STALE_LINK_NOTICE =
  "Belege müssen für diese Textversion erneut geprüft werden."

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
  const [fields, setFields] = React.useState<PortalFieldDraftDto[] | null>(null)
  const [anchors, setAnchors] = React.useState<EvidenceAnchorDto[]>([])
  const [requirements, setRequirements] = React.useState<
    RequirementAssessmentDto[] | null
  >(null)
  const [selectedId, setSelectedId] = React.useState<string | null>(null)
  const [localText, setLocalText] = React.useState("")
  const [baseVersionId, setBaseVersionId] = React.useState("")
  const [saveState, setSaveState] = React.useState<SaveState>("saved")
  const [errorMsg, setErrorMsg] = React.useState<string | null>(null)
  const [conflict, setConflict] = React.useState(false)
  const [recheck, setRecheck] = React.useState(false)
  const [loadError, setLoadError] = React.useState<string | null>(null)
  const [review, setReview] = React.useState<ReviewPackageDto | null>(null)
  const [commentText, setCommentText] = React.useState("")
  const [commentType, setCommentType] = React.useState<CommentType>("Hinweis")
  const [confirmResolveId, setConfirmResolveId] = React.useState<string | null>(null)
  const [fieldNotice, setFieldNotice] = React.useState<string | null>(null)
  // Controlled assistant tab — lets review hints open the Belege tab directly.
  const [assistantTab, setAssistantTab] = React.useState<AssistantTab | null>(null)
  // M10.3: live market comparison for the Markt tab + wide sheet.
  const [caps, setCaps] = React.useState<Capabilities | null>(null)
  const [comparison, setComparison] = React.useState<MarketComparisonDto | null>(null)
  const [comparisonLoaded, setComparisonLoaded] = React.useState(false)
  const [marketSheetOpen, setMarketSheetOpen] = React.useState(false)
  // M9D/9E: A2 draft suggestions (Solution & Innovation + Value Creation fields).
  const [a2Suggestion, setA2Suggestion] = React.useState<A2Suggestion | null>(null)
  const [a2Loading, setA2Loading] = React.useState(false)
  const [a2Unavailable, setA2Unavailable] = React.useState(false)
  const [a2Error, setA2Error] = React.useState<string | null>(null)
  const [a2ReviewOpen, setA2ReviewOpen] = React.useState(false)
  const [a2Accepting, setA2Accepting] = React.useState(false)
  const autoSelectedRef = React.useRef(false)
  const editorRef = React.useRef<RichTextEditorHandle>(null)

  const selected = fields?.find((f) => f.field_id === selectedId) ?? null
  const showA2Controls = isA2Field(selected?.field_id)
  const comparisonEnabled = caps?.features?.market_comparison === true

  React.useEffect(() => {
    let active = true
    void getCapabilities().then((c) => {
      if (active) setCaps(c)
    })
    return () => {
      active = false
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

  function resetA2() {
    setA2Suggestion(null)
    setA2Loading(false)
    setA2Unavailable(false)
    setA2Error(null)
    setA2ReviewOpen(false)
    setA2Accepting(false)
  }

  const loadReview = React.useCallback(() => {
    getReview(runId)
      .then(setReview)
      .catch(() => setReview(null))
  }, [runId])

  const load = React.useCallback(() => {
    setLoadError(null)
    setFields(null)
    Promise.all([listFields(runId), listEvidence(runId).catch(() => [])])
      .then(([drafts, ev]) => {
        setFields(drafts)
        setAnchors(ev)
        if (drafts.length && !autoSelectedRef.current) {
          autoSelectedRef.current = true
          // Deep link (?field=…) wins over the default first field; unknown
          // ids fall back silently to the first field.
          const preferred = initialFieldId
            ? drafts.find((d) => d.field_id === initialFieldId)
            : undefined
          selectField(preferred ?? drafts[0])
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

  function selectField(draft: PortalFieldDraftDto) {
    setSelectedId(draft.field_id)
    setLocalText(draft.current_version.text)
    setBaseVersionId(draft.current_version.draft_version_id)
    setSaveState("saved")
    setErrorMsg(null)
    setRecheck(false)
    setFieldNotice(null)
    setConfirmResolveId(null)
    setAssistantTab(null)
    resetA2()
  }

  async function generateSuggestion() {
    if (!selected) return
    setA2Loading(true)
    setA2Error(null)
    setA2Unavailable(false)
    try {
      const suggestion = await createRedraft(runId, selected.field_id, baseVersionId)
      setA2Suggestion(suggestion)
      setA2ReviewOpen(true)
    } catch (e) {
      if (e instanceof RedraftError && e.status === 503) {
        setA2Unavailable(true)
      } else if (e instanceof RedraftError && e.status === 409) {
        setConflict(true)
      } else {
        setA2Error(e instanceof Error ? e.message : "KI-Vorschlag fehlgeschlagen.")
      }
    } finally {
      setA2Loading(false)
    }
  }

  async function acceptSuggestion() {
    if (!selected || !a2Suggestion) return
    setA2Accepting(true)
    setErrorMsg(null)
    try {
      const updated = await updateField(
        runId,
        selected.field_id,
        a2Suggestion.base_version_id,
        a2Suggestion.suggested_text,
        a2Suggestion.operation_id
      )
      applyDraft(updated)
      setBaseVersionId(updated.current_version.draft_version_id)
      setLocalText(updated.current_version.text)
      setSaveState("saved")
      setRecheck(true)
      loadReview()
      resetA2()
    } catch (e) {
      setA2Accepting(false)
      if (e instanceof FieldError && e.status === 409) {
        setA2ReviewOpen(false)
        setConflict(true)
      } else {
        setA2Error(e instanceof FieldError ? e.message : "Übernehmen fehlgeschlagen.")
      }
    }
  }

  function dismissSuggestion() {
    // Client-side dismissal only — no backend call, no audited rejection.
    resetA2()
  }

  function applyDraft(updated: PortalFieldDraftDto) {
    setFields((prev) => (prev ?? []).map((f) => (f.field_id === updated.field_id ? updated : f)))
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
      setRecheck(true)
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
      setRecheck(true)
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

  /**
   * "Als Argument übernehmen" — inserts the sentence as a new paragraph at the
   * editor cursor (via the editor handle). The editor's onChange then updates
   * the local buffer + dirty state. Never auto-saves.
   */
  function insertMarketArgument(item: MarketComparisonItemDto) {
    editorRef.current?.insertTextAtCursor(marketArgumentSentence(item))
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
      return { label: "Belege öffnen", onClick: () => setAssistantTab("belege") }
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
      <p className="text-xs text-muted-foreground">{LINK_EXPLANATION}</p>
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
            const humanChecked = anchor?.verification_status === "human_verified"
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
                  {anchor && (
                    <Badge
                      variant={
                        anchor.verification_status === "exact_verified" || humanChecked
                          ? "default"
                          : "outline"
                      }
                    >
                      {VERIFICATION_LABELS[anchor.verification_status]}
                    </Badge>
                  )}
                  {l.status === "stale" && (
                    <Badge variant="outline">{EVIDENCE_LINK_STATUS_LABELS.stale}</Badge>
                  )}
                  {anchor && !humanChecked && (
                    <span className="text-[11px] text-muted-foreground">
                      fachliche Prüfung offen
                    </span>
                  )}
                </div>
                <div className="flex flex-wrap items-center gap-3">
                  {anchor && (
                    <a
                      href={
                        isUrl
                          ? anchor.source_name
                          : `/quellen?tab=evidenz&anchor=${encodeURIComponent(anchor.anchor_id)}`
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
        anchors.map((a) => (
          <div key={a.anchor_id} className="rounded border border-border px-2 py-2 text-xs">
            <div className="flex items-center justify-between gap-2">
              <span className="truncate text-muted-foreground">{a.source_name}</span>
              <Badge variant={a.verification_status === "exact_verified" ? "default" : "outline"}>
                {VERIFICATION_LABELS[a.verification_status]}
              </Badge>
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
    </div>
  )

  // --- Right panel: Anforderungen (per-field join via review findings) ---
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
      subtitle="Bearbeiten Sie die Texte pro Innolink-Feld, prüfen Sie KI-Vorschläge, Belege und offene Punkte."
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
        setRecheck(false)
      }}
      onSave={save}
      saveDisabled={saveState === "saving" || saveState === "saved" || overLimit}
      saveStateLabel={SAVE_STATE_LABEL[saveState]}
      deinTextBadge={
        <Badge variant="secondary">
          {CREATED_BY_LABELS[selected.current_version.created_by] ?? "Entwurf"}
        </Badge>
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
              {RECHECK_NOTICE}
            </p>
          )}
          {errorMsg && <p role="alert" className="text-xs text-destructive">{errorMsg}</p>}
        </>
      }
      editorRef={editorRef}
      serverText={selected.current_version.text}
      projectId={marketProjectId}
      kiContent={
        <div className="flex flex-col gap-2">
          {showA2Controls ? (
            <div className="flex flex-col gap-1" data-testid="a2-suggestion-control">
              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={generateSuggestion}
                  disabled={a2Loading}
                >
                  <Sparkles data-icon="inline-start" />
                  {a2Loading ? "KI-Vorschlag wird erstellt …" : "KI-Vorschlag erstellen"}
                </Button>
                {a2Suggestion && !a2ReviewOpen && (
                  <Button size="sm" variant="ghost" onClick={() => setA2ReviewOpen(true)}>
                    Vorschlag anzeigen
                  </Button>
                )}
              </div>
              {a2Unavailable && (
                <p role="status" className="text-xs text-muted-foreground">
                  KI-Vorschläge sind für diese Datenklasse oder Umgebung nicht verfügbar.
                </p>
              )}
              {!a2Suggestion && !a2Loading && !a2Unavailable && !a2Error && (
                <p className="text-xs text-muted-foreground">
                  KI-Vorschlag für diesen Abschnitt noch nicht erstellt.
                </p>
              )}
              {a2Error && <p role="alert" className="text-xs text-destructive">{a2Error}</p>}
            </div>
          ) : (
            <p
              className="text-xs text-muted-foreground"
              data-testid="a2-field-unavailable"
            >
              KI-Vorschläge sind für dieses Feld nicht verfügbar — sie unterstützen
              die Abschnitte «Lösung &amp; Innovation» und «Wertschöpfung».
            </p>
          )}
          <p className="text-[11px] text-muted-foreground">
            Vorschläge werden nie automatisch übernommen — Sie prüfen, übernehmen
            oder verwerfen selbst.
          </p>
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
          }}
          suggestionExists={false}
          belegeContent={belegeContent}
          anforderungenContent={anforderungenContent}
          kommentareContent={kommentareContent}
          versionsFootnote={
            <p className="text-xs text-muted-foreground">
              Versionshistorie ist in dieser Beta noch nicht verfügbar.
            </p>
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
            if (!o) dismissSuggestion()
          }}
          currentText={localText}
          suggestion={a2Suggestion}
          onAccept={acceptSuggestion}
          onDismiss={dismissSuggestion}
          accepting={a2Accepting}
        />
      )}
      <MarketComparisonSheet
        open={marketSheetOpen}
        onOpenChange={setMarketSheetOpen}
        comparison={comparison}
        onInsertArgument={insertMarketArgument}
      />
    </>
  )
}
