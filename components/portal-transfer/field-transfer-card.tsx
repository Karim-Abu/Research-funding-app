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
import type { PortalFieldDraftDto } from "@/lib/fields"
import type { ReviewPackageDto } from "@/lib/review"

type CopyState = "idle" | "copied" | "error"

// Compact badge labels — the shared banner above the cards carries the full
// sentences; per card we only flag which problems apply.
const WARNING_BADGE: Record<WarningCode, string> = {
  open: "Offene Angaben",
  limit: "Zeichenlimit überschritten",
  review: "Prüfung nicht aktuell",
}

export function FieldTransferCard({
  field,
  review,
  copiedAt,
  onCopied,
}: {
  field: PortalFieldDraftDto
  review: ReviewPackageDto | null
  /** When this field was copied in the current session (not persisted). */
  copiedAt: Date | null
  onCopied: (fieldId: string) => void
}) {
  const [state, setState] = React.useState<CopyState>("idle")
  const [confirming, setConfirming] = React.useState<null | "plain" | "formatted">(null)
  const [errorMsg, setErrorMsg] = React.useState<string | null>(null)
  const [advancedOpen, setAdvancedOpen] = React.useState(false)

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

  async function doCopy(kind: "plain" | "formatted") {
    setConfirming(null)
    setErrorMsg(null)
    try {
      if (kind === "formatted") await copyFormatted(text)
      else await copyPlain(text)
      setState("copied")
      onCopied(field.field_id)
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
          <div className="flex gap-2">
            <Button size="sm" onClick={() => doCopy(confirming)}>
              Trotzdem kopieren
            </Button>
            <Button size="sm" variant="outline" onClick={() => setConfirming(null)}>
              Abbrechen
            </Button>
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
    </article>
  )
}
