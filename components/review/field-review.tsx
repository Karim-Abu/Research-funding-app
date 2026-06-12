"use client"

import * as React from "react"
import {
  XCircle,
  AlertTriangle,
  ChevronRight,
  FileText,
  Loader2,
  CheckCircle2,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Textarea } from "@/components/ui/textarea"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { DraftEditor } from "@/components/editor/draft-editor"
import { MachineStatusBadge } from "@/components/status/machine-status-badge"
import { cn } from "@/lib/utils"
import type {
  EvidenceAnchorDto,
  IssueDto,
  IssueSeverity,
  PortalFieldDraftDto,
  ReviewDecisionDto,
} from "@/lib/backend-contract"

// ---------------------------------------------------------------------------
// Konfiguration (Optik folgt den bestehenden Severity-/Status-Mustern)
// ---------------------------------------------------------------------------

const FIELD_STATUS_CONFIG: Record<
  PortalFieldDraftDto["status"],
  { label: string; className: string }
> = {
  ready: {
    label: "Bereit",
    className: "bg-status-fulfilled/12 text-status-fulfilled",
  },
  needs_review: {
    label: "Zu prüfen",
    className: "bg-status-partial/12 text-status-partial",
  },
  blocked: {
    label: "Blockiert",
    className: "bg-status-blocker/12 text-status-blocker",
  },
}

const ISSUE_SEVERITY_CONFIG: Record<
  IssueSeverity,
  { label: string; className: string; icon: React.ElementType }
> = {
  blocker: {
    label: "Blockierend",
    className: "bg-status-blocker/12 text-status-blocker",
    icon: XCircle,
  },
  warning: {
    label: "Warnung",
    className: "bg-status-partial/12 text-status-partial",
    icon: AlertTriangle,
  },
  info: {
    label: "Hinweis",
    className: "bg-muted text-muted-foreground",
    icon: ChevronRight,
  },
}

// ---------------------------------------------------------------------------
// Evidence anchor line (no confidence values anywhere)
// ---------------------------------------------------------------------------

function EvidenceAnchorLine({ anchor }: { anchor: EvidenceAnchorDto }) {
  return (
    <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
      <FileText className="size-3.5 shrink-0" />
      <span className="truncate">
        {anchor.sourceTitle} · {anchor.location}
      </span>
      <MachineStatusBadge
        status={anchor.verified ? "verified" : "open"}
        className="shrink-0"
      />
    </span>
  )
}

// ---------------------------------------------------------------------------
// FieldReview — 3 Spalten: Feldliste / editierbarer Text / Issue-Panel
// ---------------------------------------------------------------------------

export interface FieldReviewProps {
  fields: PortalFieldDraftDto[]
  issues: IssueDto[]
  /** true, während eine Review-Entscheidung/Prüfung läuft. */
  busy: boolean
  /** "Änderungen prüfen" für ein editiertes Feld. */
  onRecheck: (fieldId: string, text: string) => void
  /** Einzel- oder Sammel-Entscheidungen (confirm/override). */
  onDecide: (decisions: ReviewDecisionDto["decisions"]) => void
  /** Wird unter dem Issue-Panel gerendert (Freigabe-Karte). */
  approvalSlot?: React.ReactNode
}

export function FieldReview({
  fields,
  issues,
  busy,
  onRecheck,
  onDecide,
  approvalSlot,
}: FieldReviewProps) {
  const firstBlocked = fields.find((f) => f.status === "blocked")
  const [activeFieldId, setActiveFieldId] = React.useState(
    (firstBlocked ?? fields[0])?.fieldId ?? ""
  )
  // Edit buffer per field; "dirty" = buffer differs from the server text.
  const [drafts, setDrafts] = React.useState<Record<string, string>>({})
  const [selectedWarnings, setSelectedWarnings] = React.useState<Set<string>>(
    new Set()
  )
  // Override dialog
  const [overrideIssueId, setOverrideIssueId] = React.useState<string | null>(
    null
  )
  const [overrideComment, setOverrideComment] = React.useState("")

  const activeField = fields.find((f) => f.fieldId === activeFieldId) ?? fields[0]
  if (!activeField) return null

  const draftText = drafts[activeField.fieldId] ?? activeField.text
  const charCount = draftText.trimEnd().length
  // charLimit === null -> "Kein Limit", nie rotes Styling.
  const overLimit =
    activeField.charLimit !== null && charCount > activeField.charLimit
  const isDirty = draftText !== activeField.text

  const openBlockers = issues.filter(
    (i) => i.severity === "blocker" && i.state === "open"
  )
  const decidedBlockers = issues.filter(
    (i) => i.severity === "blocker" && i.state !== "open"
  )
  const openWarnings = issues.filter(
    (i) => i.severity === "warning" && i.state === "open"
  )
  const decidedWarnings = issues.filter(
    (i) => i.severity === "warning" && i.state !== "open"
  )
  const infos = issues.filter((i) => i.severity === "info")

  function fieldName(fieldId: string): string {
    return fields.find((f) => f.fieldId === fieldId)?.name ?? fieldId
  }

  function toggleWarning(id: string) {
    setSelectedWarnings((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  function confirmSelectedWarnings() {
    const decisions = [...selectedWarnings].map((issueId) => ({
      issueId,
      action: "confirm" as const,
    }))
    setSelectedWarnings(new Set())
    onDecide(decisions)
  }

  function submitOverride() {
    if (!overrideIssueId || !overrideComment.trim()) return
    onDecide([
      {
        issueId: overrideIssueId,
        action: "override",
        comment: overrideComment.trim(),
      },
    ])
    setOverrideIssueId(null)
    setOverrideComment("")
  }

  return (
    <div className="flex items-start gap-6">
      {/* Left: field list */}
      <nav aria-label="Felder" className="flex w-60 shrink-0 flex-col gap-1">
        {fields.map((field) => {
          const cfg = FIELD_STATUS_CONFIG[field.status]
          const active = field.fieldId === activeField.fieldId
          return (
            <button
              key={field.fieldId}
              type="button"
              onClick={() => setActiveFieldId(field.fieldId)}
              className={cn(
                "flex flex-col gap-1 rounded-md border px-3 py-2 text-left transition-colors",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                active
                  ? "border-primary bg-accent/40"
                  : "border-border bg-card hover:border-primary/40"
              )}
            >
              <span className="text-sm font-medium leading-snug text-foreground">
                {field.name}
              </span>
              <span
                className={cn(
                  "inline-flex w-fit items-center rounded-full px-2 py-0.5 text-xs font-medium",
                  cfg.className
                )}
              >
                {cfg.label}
              </span>
            </button>
          )
        })}
      </nav>

      {/* Middle: editable field text + live counter + evidence */}
      <div className="flex min-w-0 flex-1 flex-col gap-3">
        <div className="flex items-center justify-between gap-3">
          <h3 className="text-sm font-semibold text-foreground">
            {activeField.name}
          </h3>
          <span
            className={cn(
              "shrink-0 text-xs",
              overLimit
                ? "font-medium text-status-blocker"
                : "text-muted-foreground"
            )}
          >
            {activeField.charLimit === null
              ? `${charCount.toLocaleString("de-CH")} · Kein Limit`
              : `${charCount.toLocaleString("de-CH")} / ${activeField.charLimit.toLocaleString("de-CH")}`}
          </span>
        </div>

        <DraftEditor
          draftText={draftText}
          onChange={(value) =>
            setDrafts((prev) => ({ ...prev, [activeField.fieldId]: value }))
          }
        />

        {isDirty && (
          <Button
            size="sm"
            className="self-start"
            disabled={busy}
            onClick={() => onRecheck(activeField.fieldId, draftText)}
          >
            {busy ? (
              <>
                <Loader2 data-icon="inline-start" className="animate-spin" />
                Wird geprüft…
              </>
            ) : (
              "Änderungen prüfen"
            )}
          </Button>
        )}

        {activeField.evidence.length > 0 && (
          <div className="flex flex-col gap-1.5 rounded-md border border-border bg-muted/20 p-3">
            <span className="text-xs font-semibold text-foreground">
              Belege für dieses Feld
            </span>
            {activeField.evidence.map((anchor) => (
              <EvidenceAnchorLine key={anchor.anchorId} anchor={anchor} />
            ))}
          </div>
        )}
      </div>

      {/* Right: issue panel + approval slot */}
      <div className="flex w-80 shrink-0 flex-col gap-4">
        <IssueGroup title={`Blockierende Punkte (${openBlockers.length})`}>
          {openBlockers.length === 0 && decidedBlockers.length === 0 && (
            <p className="text-xs text-muted-foreground">
              Keine blockierenden Punkte.
            </p>
          )}
          {openBlockers.map((issue) => (
            <IssueCard
              key={issue.id}
              issue={issue}
              fieldName={fieldName(issue.fieldId)}
              onSelectField={() => setActiveFieldId(issue.fieldId)}
              actions={
                <div className="flex gap-2">
                  <Button
                    size="xs"
                    variant="outline"
                    disabled={busy}
                    onClick={() =>
                      onDecide([{ issueId: issue.id, action: "confirm" }])
                    }
                  >
                    Als behoben markieren
                  </Button>
                  <Button
                    size="xs"
                    variant="outline"
                    disabled={busy}
                    onClick={() => setOverrideIssueId(issue.id)}
                  >
                    Überschreiben…
                  </Button>
                </div>
              }
            />
          ))}
          {decidedBlockers.map((issue) => (
            <IssueCard
              key={issue.id}
              issue={issue}
              fieldName={fieldName(issue.fieldId)}
              onSelectField={() => setActiveFieldId(issue.fieldId)}
            />
          ))}
        </IssueGroup>

        <IssueGroup title={`Warnungen (${openWarnings.length})`}>
          {openWarnings.length === 0 && decidedWarnings.length === 0 && (
            <p className="text-xs text-muted-foreground">Keine Warnungen.</p>
          )}
          {openWarnings.map((issue) => (
            <IssueCard
              key={issue.id}
              issue={issue}
              fieldName={fieldName(issue.fieldId)}
              onSelectField={() => setActiveFieldId(issue.fieldId)}
              leading={
                <Checkbox
                  checked={selectedWarnings.has(issue.id)}
                  onCheckedChange={() => toggleWarning(issue.id)}
                  aria-label={`Warnung auswählen: ${issue.title}`}
                  className="mt-0.5"
                />
              }
            />
          ))}
          {openWarnings.length > 0 && (
            <Button
              size="xs"
              variant="outline"
              className="self-start"
              disabled={busy || selectedWarnings.size === 0}
              onClick={confirmSelectedWarnings}
            >
              {`Ausgewählte bestätigen (${selectedWarnings.size})`}
            </Button>
          )}
          {decidedWarnings.map((issue) => (
            <IssueCard
              key={issue.id}
              issue={issue}
              fieldName={fieldName(issue.fieldId)}
              onSelectField={() => setActiveFieldId(issue.fieldId)}
            />
          ))}
        </IssueGroup>

        <IssueGroup title={`Hinweise (${infos.length})`}>
          {infos.length === 0 && (
            <p className="text-xs text-muted-foreground">Keine Hinweise.</p>
          )}
          {infos.map((issue) => (
            <IssueCard
              key={issue.id}
              issue={issue}
              fieldName={fieldName(issue.fieldId)}
              onSelectField={() => setActiveFieldId(issue.fieldId)}
            />
          ))}
        </IssueGroup>

        {approvalSlot}
      </div>

      {/* Override dialog — mandatory comment */}
      <Dialog
        open={overrideIssueId !== null}
        onOpenChange={(open) => {
          if (!open) {
            setOverrideIssueId(null)
            setOverrideComment("")
          }
        }}
      >
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Blocker überschreiben</DialogTitle>
            <DialogDescription>
              Begründen Sie, warum dieser Punkt trotz Blockierung akzeptiert
              wird. Der Kommentar ist für alle Projektmitglieder sichtbar.
            </DialogDescription>
          </DialogHeader>
          <Textarea
            value={overrideComment}
            onChange={(e) => setOverrideComment(e.target.value)}
            placeholder="Kommentar (Pflichtfeld)…"
            className="min-h-[100px]"
          />
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setOverrideIssueId(null)
                setOverrideComment("")
              }}
            >
              Abbrechen
            </Button>
            <Button
              disabled={!overrideComment.trim() || busy}
              onClick={submitOverride}
            >
              Überschreiben
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Issue group + card
// ---------------------------------------------------------------------------

function IssueGroup({
  title,
  children,
}: {
  title: string
  children: React.ReactNode
}) {
  return (
    <section className="flex flex-col gap-2">
      <h3 className="text-sm font-semibold text-foreground">{title}</h3>
      {children}
    </section>
  )
}

function IssueCard({
  issue,
  fieldName,
  onSelectField,
  actions,
  leading,
}: {
  issue: IssueDto
  fieldName: string
  onSelectField: () => void
  actions?: React.ReactNode
  leading?: React.ReactNode
}) {
  const cfg = ISSUE_SEVERITY_CONFIG[issue.severity]
  const Icon = cfg.icon
  const decided = issue.state !== "open"

  return (
    <div
      className={cn(
        "flex flex-col gap-1.5 rounded-md border border-border bg-card px-3 py-2.5",
        decided && "opacity-70"
      )}
    >
      <div className="flex items-start gap-2">
        {leading}
        <div className="flex min-w-0 flex-1 flex-col gap-1">
          <div className="flex flex-wrap items-center gap-1.5">
            <span
              className={cn(
                "inline-flex shrink-0 items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium",
                cfg.className
              )}
            >
              <Icon className="size-3" />
              {cfg.label}
            </span>
            <span className="text-sm font-medium text-foreground">
              {issue.title}
            </span>
          </div>
          <p className="text-xs leading-relaxed text-muted-foreground">
            {issue.description}
          </p>
          <button
            type="button"
            onClick={onSelectField}
            className="self-start text-xs text-muted-foreground underline-offset-2 hover:text-foreground hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            {`Zum Feld: ${fieldName}`}
          </button>
          {issue.evidence?.map((anchor) => (
            <EvidenceAnchorLine key={anchor.anchorId} anchor={anchor} />
          ))}
          {issue.state === "confirmed" && (
            <span className="inline-flex items-center gap-1 text-xs text-status-fulfilled">
              <CheckCircle2 className="size-3.5" />
              Bestätigt
            </span>
          )}
          {issue.state === "overridden" && (
            <span className="text-xs text-muted-foreground">
              {`Überschrieben von ${issue.overriddenBy ?? "—"}: «${issue.overrideComment ?? ""}»`}
            </span>
          )}
        </div>
      </div>
      {actions}
    </div>
  )
}
