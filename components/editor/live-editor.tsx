"use client"

import * as React from "react"
import { Link2, RefreshCw, Trash2 } from "lucide-react"
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
  VERIFICATION_LABELS,
  EVIDENCE_LINK_STATUS_LABELS,
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
import { DraftWorkspaceShell } from "@/components/editor/draft-workspace-shell"
import { AssistantPanel } from "@/components/editor/assistant-panel"
import { SuggestionReviewDialog } from "@/components/editor/suggestion-review-dialog"
import { liveFieldToViewModel, pickDefaultTab } from "@/lib/draft-viewmodel"
import { AI_GOALS, AI_LIVE_NOTICE } from "@/lib/draft-ai-actions"
import {
  createRedraft,
  RedraftError,
  SOLUTION_INNOVATION_FIELD_ID,
  type A2Suggestion,
} from "@/lib/redraft"
import { Sparkles } from "lucide-react"

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

export function LiveEditor({ runId }: { runId: string }) {
  const [fields, setFields] = React.useState<PortalFieldDraftDto[] | null>(null)
  const [anchors, setAnchors] = React.useState<EvidenceAnchorDto[]>([])
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
  const [fieldNotice, setFieldNotice] = React.useState<string | null>(null)
  // M9D: A2 draft suggestions (Solution & Innovation field only).
  const [a2Suggestion, setA2Suggestion] = React.useState<A2Suggestion | null>(null)
  const [a2Loading, setA2Loading] = React.useState(false)
  const [a2Unavailable, setA2Unavailable] = React.useState(false)
  const [a2Error, setA2Error] = React.useState<string | null>(null)
  const [a2ReviewOpen, setA2ReviewOpen] = React.useState(false)
  const [a2Accepting, setA2Accepting] = React.useState(false)
  const autoSelectedRef = React.useRef(false)

  const selected = fields?.find((f) => f.field_id === selectedId) ?? null
  const isSolutionField = selected?.field_id === SOLUTION_INNOVATION_FIELD_ID

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
          selectField(drafts[0])
        }
      })
      .catch((e) =>
        setLoadError(e instanceof Error ? e.message : "Entwürfe konnten nicht geladen werden.")
      )
    loadReview()
  }, [runId, loadReview])

  React.useEffect(() => load(), [load])

  function selectField(draft: PortalFieldDraftDto) {
    setSelectedId(draft.field_id)
    setLocalText(draft.current_version.text)
    setBaseVersionId(draft.current_version.draft_version_id)
    setSaveState("saved")
    setErrorMsg(null)
    setRecheck(false)
    setFieldNotice(null)
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
        comment: commentText.trim(),
      })
      setCommentText("")
      loadReview()
    } catch (e) {
      setErrorMsg(e instanceof Error ? e.message : "Kommentar fehlgeschlagen.")
    }
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

  const viewModels = fields.map((f) => liveFieldToViewModel(f, review))
  const activeVm = viewModels.find((v) => v.id === selected.field_id) ?? viewModels[0]

  const hasBlocker = (review?.blocker_count ?? 0) > 0 || selectedFindings.some((f) => f.severity === "blocker")
  const defaultTab = pickDefaultTab(activeVm, {
    hasMarketData: false,
    hasFindings: selectedFindings.length > 0,
    hasBlocker,
  })

  // --- Right panel: Belege (live evidence + linking) ---
  const belegeContent = (
    <div className="flex flex-col gap-3">
      <p className="text-xs text-muted-foreground">{LINK_EXPLANATION}</p>
      {hasStaleLink && (
        <p className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-900">
          {STALE_LINK_NOTICE}
        </p>
      )}
      {draftLinks.length > 0 && (
        <ul className="flex flex-col gap-1">
          {draftLinks.map((l) => (
            <li
              key={l.evidence_link_id}
              className="flex items-center justify-between gap-2 rounded border border-border px-2 py-1 text-xs"
            >
              <span>
                Verknüpfung{" "}
                <span className="text-muted-foreground">
                  ({EVIDENCE_LINK_STATUS_LABELS[l.status]})
                </span>
              </span>
              {l.status !== "removed" && (
                <Button
                  variant="ghost"
                  size="xs"
                  aria-label="Verknüpfung entfernen"
                  onClick={() => unlink(l.evidence_link_id)}
                >
                  <Trash2 className="size-3" />
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
      {anchors.length === 0 ? (
        <p className="text-xs text-muted-foreground">
          Noch keine Belege mit diesem Feld verknüpft.
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
            {selectedFindings.map((f) => (
              <li
                key={f.finding_id}
                className="flex items-start justify-between gap-2 rounded border border-border px-2 py-1 text-xs"
              >
                <span>
                  <Badge
                    variant={f.severity === "blocker" ? "destructive" : "outline"}
                    className="mr-1 align-middle"
                  >
                    {f.severity === "blocker" ? "Blocker" : "Hinweis"}
                  </Badge>
                  {f.description}
                </span>
                <Button variant="ghost" size="xs" onClick={() => resolveFinding(f.finding_id)}>
                  Erledigt
                </Button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <Textarea
        value={commentText}
        onChange={(e) => setCommentText(e.target.value)}
        rows={2}
        aria-label="Kommentar zum Abschnitt"
        placeholder="Kommentar zum Abschnitt hinzufügen …"
        className="text-sm"
      />
      <div className="flex items-center justify-between gap-2">
        <Button size="sm" variant="outline" onClick={addComment} disabled={!commentText.trim()}>
          Kommentar hinzufügen
        </Button>
        <Button size="sm" onClick={approveField} disabled={!fieldApprovable}>
          Abschnitt freigeben
        </Button>
      </div>
      {fieldNotice && <p role="status" className="text-xs text-emerald-700">{fieldNotice}</p>}
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
      deinTextBadge={<Badge variant="secondary">Strukturvorlage</Badge>}
      deinTextHint={
        <p className="text-xs text-muted-foreground">Bitte fachlich prüfen und ergänzen.</p>
      }
      noticeSlot={
        <>
          {isSolutionField && (
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
          )}
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
      aiActions={AI_GOALS}
      aiEnabled={false}
      aiHint={AI_LIVE_NOTICE}
      onAiAction={() => undefined}
      suggestion={null}
      onAcceptAll={() => undefined}
      onAcceptParagraph={() => undefined}
      onToggleCompare={() => undefined}
      compareOpen={false}
      onDiscard={() => undefined}
      assistant={
        <AssistantPanel
          key={selected.field_id}
          vm={activeVm}
          defaultTab={defaultTab}
          market={{ data: null, relevant: activeVm.isMarketRelevant, live: true }}
          suggestionExists={false}
          belegeContent={belegeContent}
          kommentareContent={kommentareContent}
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
    </>
  )
}
