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

type SaveState = "saved" | "dirty" | "saving" | "error"

const SECTION: Record<string, string> = {
  INTRO: "Einleitung",
  ORG: "Organisation & Partner",
  VC: "Wertschöpfung",
  SOL: "Lösung & Innovation",
  PS: "Projektplan",
}

function sectionOf(fieldId: string): string {
  return SECTION[fieldId.split(".")[0]] ?? "Weitere"
}

const RECHECK_NOTICE =
  "Änderungen gespeichert. Eine erneute Prüfung ist vor der Freigabe erforderlich."
const LINK_EXPLANATION =
  "Die Verknüpfung ordnet eine Fundstelle diesem Entwurf zu. Sie bestätigt nicht automatisch den gesamten Text."
const STALE_LINK_NOTICE =
  "Belege müssen für diese Textversion erneut geprüft werden."

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
  // Guards the initial auto-select so a duplicate/late load resolution (e.g. the
  // React StrictMode double-invoke of the load effect) can never re-select the
  // first field and clobber an in-progress edit.
  const autoSelectedRef = React.useRef(false)

  const selected = fields?.find((f) => f.field_id === selectedId) ?? null

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
  }

  function applyDraft(updated: PortalFieldDraftDto) {
    setFields((prev) =>
      (prev ?? []).map((f) => (f.field_id === updated.field_id ? updated : f))
    )
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
        setConflict(true) // keep local text — never overwrite
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
      <div className="grid gap-4 lg:grid-cols-[240px_1fr]">
        <Skeleton className="h-72 w-full" />
        <Skeleton className="h-72 w-full" />
      </div>
    )
  }

  const limit = selected?.character_limit ?? null
  const count = charCount(localText)
  const overLimit = limit != null && count > limit
  const draftLinks = selected?.evidence_links ?? []
  const hasStaleLink = draftLinks.some((l) => l.status === "stale")
  const linkedAnchorIds = new Set(
    draftLinks.filter((l) => l.status === "active").map((l) => l.anchor_id)
  )

  return (
    <div className="grid gap-6 lg:grid-cols-[240px_1fr_300px]">
      {/* Field selector */}
      <nav aria-label="Abschnitte" className="flex flex-col gap-1">
        {fields.map((f) => (
          <button
            key={f.field_id}
            type="button"
            onClick={() => selectField(f)}
            className={`rounded-md px-3 py-2 text-left text-sm transition-colors ${
              f.field_id === selectedId ? "bg-accent font-medium" : "hover:bg-accent/50"
            }`}
          >
            <span className="block text-xs text-muted-foreground">
              {sectionOf(f.field_id)}
            </span>
            {f.field_name}
          </button>
        ))}
      </nav>

      {/* Editor */}
      {selected ? (
        <div className="flex min-w-0 flex-col gap-3">
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-semibold">{selected.field_name}</h2>
            <Badge variant="secondary">Strukturvorlage</Badge>
          </div>
          <p className="text-xs text-muted-foreground">
            Bitte fachlich prüfen und ergänzen.
          </p>
          <Textarea
            value={localText}
            onChange={(e) => {
              setLocalText(e.target.value)
              setSaveState("dirty")
              setRecheck(false)
            }}
            rows={14}
            aria-label={`Entwurf ${selected.field_name}`}
            className="font-mono text-sm"
          />
          <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
            <span className={overLimit ? "text-destructive" : "text-muted-foreground"}>
              {count}
              {limit != null ? ` / ${limit}` : ""} Zeichen
            </span>
            <div className="flex items-center gap-2">
              <span className="text-muted-foreground">
                {saveState === "saving"
                  ? "Speichert …"
                  : saveState === "dirty"
                    ? "Änderungen"
                    : saveState === "error"
                      ? "Fehler"
                      : "Gespeichert"}
              </span>
              <Button
                size="sm"
                onClick={save}
                disabled={saveState === "saving" || saveState === "saved" || overLimit}
              >
                Speichern
              </Button>
            </div>
          </div>
          {errorMsg && (
            <p role="alert" className="text-xs text-destructive">
              {errorMsg}
            </p>
          )}
          {recheck && (
            <p
              role="status"
              className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-900"
            >
              {RECHECK_NOTICE}
            </p>
          )}

          {/* Aktuelle Version (Verlauf intern; nur aktuelle Metadaten sichtbar) */}
          <div className="rounded-md border border-border px-3 py-2 text-xs text-muted-foreground">
            <span className="font-medium text-foreground">Aktuelle Version</span>
            {" · "}
            {selected.current_version.created_by === "user" ? "bearbeitet" : "Vorlage"}
            {" · "}
            {new Date(selected.current_version.created_at).toLocaleString("de-CH")}
            {" · "}
            {selected.current_version.character_count} Zeichen
            {" · "}
            {draftLinks.filter((l) => l.status === "active").length} Belege
          </div>

          {/* Review-Hinweise + Abschnittskommentare */}
          <section aria-label="Review-Hinweise" className="flex flex-col gap-2">
            <h3 className="text-sm font-semibold">Review &amp; Kommentare</h3>
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
                    <Button
                      variant="ghost"
                      size="xs"
                      onClick={() => resolveFinding(f.finding_id)}
                    >
                      Erledigt
                    </Button>
                  </li>
                ))}
              </ul>
            )}
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
            {fieldNotice && (
              <p role="status" className="text-xs text-emerald-700">
                {fieldNotice}
              </p>
            )}
            {!fieldApprovable && review && !review.recheck_required && (
              <p className="text-xs text-muted-foreground">
                Freigabe möglich, sobald keine Blocker-Hinweise für diesen Abschnitt
                offen sind.
              </p>
            )}
          </section>
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">Kein Abschnitt ausgewählt.</p>
      )}

      {/* Evidence panel */}
      <aside aria-label="Belege" className="flex flex-col gap-3">
        <h3 className="text-sm font-semibold">Belege</h3>
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
        <div className="flex flex-col gap-2">
          {anchors.length === 0 && (
            <p className="text-xs text-muted-foreground">Keine Fundstellen vorhanden.</p>
          )}
          {anchors.map((a) => (
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
          ))}
        </div>
      </aside>

      {/* Conflict dialog — never overwrites local text */}
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
    </div>
  )
}
