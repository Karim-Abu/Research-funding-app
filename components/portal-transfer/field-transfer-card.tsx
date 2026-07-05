"use client"

import * as React from "react"
import { Copy, Check, ChevronDown, ChevronRight, Pencil } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import {
  copyPlain,
  copyFormatted,
  formattedCopySupported,
} from "@/lib/clipboard"
import {
  countPlaceholders,
  fieldWarnings,
  isComposite,
  sectionLabel,
  type WarningCode,
} from "@/lib/portal-transfer"
import {
  FieldError,
  recordCopyEvent,
  type OverrideReasonCode,
  type PortalFieldDraftDto,
} from "@/lib/fields"
import type { ReviewPackageDto } from "@/lib/review"

type CopyState = "idle" | "copied" | "error"

// Compact badge labels — the shared banner above the cards carries the full
// sentences; per card we only flag which problems apply.
const WARNING_BADGE: Record<WarningCode, string> = {
  open: "Offene Angaben",
  limit: "Zeichenlimit überschritten",
  review: "Prüfung nicht aktuell",
}

// Slice 3 (E2-A): predefined override reasons — a copy despite warnings needs
// a documented reason; "Sonstiges" additionally needs a short free text.
const OVERRIDE_REASONS: Array<{ code: OverrideReasonCode; label: string }> = [
  { code: "portal_finalization", label: "Feld wird im Portal fertiggestellt" },
  { code: "warning_not_relevant", label: "Hinweis betrifft dieses Feld nicht" },
  { code: "coordination_draft", label: "Zwischenstand für Abstimmung" },
  { code: "other", label: "Sonstiges" },
]

const LOG_FAILED_NOTE = "Übernahme konnte nicht protokolliert werden."
const STALE_NOTE =
  "Der Feldtext wurde zwischenzeitlich geändert und wird neu geladen. " +
  "Bitte prüfen Sie den aktuellen Stand."

export function FieldTransferCard({
  field,
  review,
  copiedAt,
  onCopied,
  runId = null,
  copyEventsEnabled = false,
  onReload,
}: {
  field: PortalFieldDraftDto
  review: ReviewPackageDto | null
  /** When this field was copied (server CopyEvent time or session fallback). */
  copiedAt: Date | null
  onCopied: (fieldId: string, at?: Date) => void
  /** Slice 3: with runId + copyEventsEnabled each copy is recorded server-side. */
  runId?: string | null
  copyEventsEnabled?: boolean
  onReload?: () => void
}) {
  const [state, setState] = React.useState<CopyState>("idle")
  const [confirming, setConfirming] = React.useState<null | "plain" | "formatted">(null)
  const [errorMsg, setErrorMsg] = React.useState<string | null>(null)
  const [infoMsg, setInfoMsg] = React.useState<string | null>(null)
  const [advancedOpen, setAdvancedOpen] = React.useState(false)
  const [reasonCode, setReasonCode] = React.useState<OverrideReasonCode | null>(null)
  const [reasonNote, setReasonNote] = React.useState("")

  const text = field.current_version.text
  const warnings = fieldWarnings(field, review)
  const copyReady = warnings.length === 0
  const placeholderCount = countPlaceholders(text)
  const limit = field.character_limit
  const overLimit = limit != null && field.character_count > limit
  const formatted = formattedCopySupported()
  const modified = new Date(field.current_version.created_at).toLocaleString("de-CH")
  // Deep link into the draft editor with this field preselected.
  const editorHref = `/editor?field=${encodeURIComponent(field.field_id)}`

  // Server-side copy logging is active only on live pages with the feature
  // enabled; without it the card behaves exactly as before (no network call).
  const loggingActive = Boolean(runId) && copyEventsEnabled
  const needsReason = loggingActive && warnings.length > 0
  const reasonMissing =
    needsReason &&
    (reasonCode === null || (reasonCode === "other" && reasonNote.trim() === ""))

  async function doCopy(kind: "plain" | "formatted") {
    setErrorMsg(null)
    setInfoMsg(null)
    let copiedAtDate: Date | undefined
    if (loggingActive && runId) {
      try {
        const event = await recordCopyEvent(runId, field.field_id, {
          draft_version_id: field.current_version.draft_version_id,
          client_warnings: warnings.map((w) => w.code),
          ...(needsReason && reasonCode
            ? {
                override_reason_code: reasonCode,
                ...(reasonCode === "other"
                  ? { override_reason_note: reasonNote.trim() }
                  : {}),
              }
            : {}),
        })
        copiedAtDate = new Date(event.created_at)
      } catch (e) {
        if (e instanceof FieldError && e.status === 409) {
          // The shown text is outdated — do NOT copy it; reload instead.
          setConfirming(null)
          setInfoMsg(STALE_NOTE)
          onReload?.()
          return
        }
        if (e instanceof FieldError && e.status === 422) {
          // Missing reason — keep the dialog open so the user can pick one.
          setInfoMsg(
            reasonCode === "other"
              ? "Bitte ergänzen Sie eine kurze Begründung."
              : "Bitte wählen Sie einen Grund aus."
          )
          return
        }
        // Fail-open (E2-A): logging problems never block the copy itself.
        setInfoMsg(LOG_FAILED_NOTE)
      }
    }
    setConfirming(null)
    setReasonCode(null)
    setReasonNote("")
    try {
      if (kind === "formatted") await copyFormatted(text)
      else await copyPlain(text)
      setState("copied")
      // "Kopiert am" only after the clipboard write actually succeeded.
      onCopied(field.field_id, copiedAtDate)
    } catch {
      setState("error")
      setErrorMsg(
        "Automatisches Kopieren ist nicht möglich. Bitte markieren Sie den Text und kopieren Sie ihn manuell."
      )
    }
  }

  function requestCopy(kind: "plain" | "formatted") {
    if (warnings.length > 0) setConfirming(kind)
    else doCopy(kind)
  }

  function cancelConfirm() {
    setConfirming(null)
    setInfoMsg(null)
    setReasonCode(null)
    setReasonNote("")
  }

  return (
    <article className="flex flex-col gap-2 rounded-lg border border-border bg-card p-4">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <span className="block text-xs text-muted-foreground">
            {sectionLabel(field.field_id)}
            {isComposite(field.field_id) && " · Mehrteiliges Feld"}
          </span>
          <h3 className="text-sm font-semibold">{field.field_name}</h3>
        </div>
        {copiedAt && (
          <Badge variant="secondary" className="shrink-0">
            <Check className="mr-1 size-3" />
            {`Kopiert am ${copiedAt.toLocaleDateString("de-CH", { day: "2-digit", month: "2-digit" })}, ${copiedAt.toLocaleTimeString("de-CH", { hour: "2-digit", minute: "2-digit" })}`}
          </Badge>
        )}
      </div>

      {/* Draft text — rendered as a React text node (auto-escaped), never innerHTML. */}
      <div className="max-h-48 overflow-auto whitespace-pre-wrap rounded border border-border bg-muted/30 p-2 font-mono text-xs">
        {text}
      </div>

      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
        <span className={overLimit ? "text-destructive" : undefined}>
          {field.character_count}
          {limit != null ? ` / ${limit}` : ""} Zeichen
        </span>
        {placeholderCount > 0 && <span>{placeholderCount} Platzhalter</span>}
        {field.open_issue_count > 0 && <span>{field.open_issue_count} offene Hinweise</span>}
        <span>Zuletzt geändert: {modified}</span>
        {/* Compact warning badges — full sentences live in the shared banner. */}
        {warnings.map((w) => (
          <Badge
            key={w.code}
            variant="outline"
            className="border-amber-300 bg-amber-50 text-amber-900"
          >
            {WARNING_BADGE[w.code]}
          </Badge>
        ))}
      </div>

      {confirming ? (
        <div className="flex flex-col gap-2 rounded border border-amber-300 bg-amber-50 px-2 py-2 text-xs text-amber-900">
          <span>
            Dieses Feld enthält noch offene Angaben. Kopieren Sie es nur bewusst
            als Entwurf.
          </span>
          <ul className="flex flex-col gap-0.5">
            {warnings.map((w) => (
              <li key={w.code}>• {w.message}</li>
            ))}
          </ul>
          {needsReason && (
            <fieldset className="flex flex-col gap-1">
              <legend className="font-semibold">
                Grund für Übernahme trotz Hinweisen
              </legend>
              {OVERRIDE_REASONS.map((reason) => (
                <label key={reason.code} className="flex items-center gap-2">
                  <input
                    type="radio"
                    name={`copy-reason-${field.field_id}`}
                    checked={reasonCode === reason.code}
                    onChange={() => {
                      setReasonCode(reason.code)
                      setInfoMsg(null)
                    }}
                  />
                  {reason.label}
                </label>
              ))}
              {reasonCode === "other" && (
                <div className="flex flex-col gap-1 pl-5">
                  <input
                    type="text"
                    value={reasonNote}
                    onChange={(e) => setReasonNote(e.target.value)}
                    maxLength={200}
                    placeholder="Kurze Begründung"
                    aria-label="Kurze Begründung"
                    className="rounded border border-amber-300 bg-white px-2 py-1 text-xs text-foreground"
                  />
                  <span>Keine vertraulichen Inhalte eingeben.</span>
                </div>
              )}
            </fieldset>
          )}
          {infoMsg && <p role="status">{infoMsg}</p>}
          <div className="flex flex-wrap items-center gap-2">
            <Button
              size="sm"
              disabled={reasonMissing}
              onClick={() => doCopy(confirming)}
            >
              Trotzdem kopieren
            </Button>
            <Button size="sm" variant="outline" onClick={cancelConfirm}>
              Abbrechen
            </Button>
            {reasonMissing && (
              <span>
                {reasonCode === "other"
                  ? "Bitte ergänzen Sie eine kurze Begründung."
                  : "Bitte wählen Sie zuerst einen Grund aus."}
              </span>
            )}
          </div>
        </div>
      ) : (
        <div className="flex flex-col gap-1.5">
          {/* Button weighting depends on readiness: copy-ready fields lead with
              the copy action; open fields lead back into the draft. */}
          <div className="flex flex-wrap items-center gap-2">
            {copyReady ? (
              <>
                <Button size="sm" onClick={() => requestCopy("plain")}>
                  <Copy data-icon="inline-start" />
                  Text kopieren
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  render={<a href={editorHref} />}
                  nativeButton={false}
                >
                  Im Entwurf öffnen
                </Button>
              </>
            ) : (
              <>
                <Button
                  size="sm"
                  render={<a href={editorHref} />}
                  nativeButton={false}
                >
                  <Pencil data-icon="inline-start" />
                  Im Entwurf bearbeiten
                </Button>
                <Button size="sm" variant="outline" onClick={() => requestCopy("plain")}>
                  <Copy data-icon="inline-start" />
                  Trotzdem kopieren…
                </Button>
              </>
            )}
          </div>
          {/* Experimental formatted copy stays behind an "Erweitert" disclosure. */}
          {formatted && (
            <div>
              <button
                type="button"
                onClick={() => setAdvancedOpen((v) => !v)}
                aria-expanded={advancedOpen}
                className="flex items-center gap-1 rounded text-xs text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                {advancedOpen ? (
                  <ChevronDown className="size-3.5" />
                ) : (
                  <ChevronRight className="size-3.5" />
                )}
                Erweitert
              </button>
              {advancedOpen && (
                <div className="mt-1.5">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => requestCopy("formatted")}
                  >
                    Formatiert kopieren (experimentell)
                  </Button>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {state === "error" && errorMsg && (
        <p role="alert" className="text-xs text-destructive">
          {errorMsg}
        </p>
      )}
      {/* Logging/stale notices outside the dialog (fail-open + 409 path). */}
      {!confirming && infoMsg && (
        <p role="status" className="text-xs text-amber-900">
          {infoMsg}
        </p>
      )}
    </article>
  )
}
