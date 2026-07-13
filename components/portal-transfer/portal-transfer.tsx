"use client"

import * as React from "react"
import { AlertTriangle, Copy, Info } from "lucide-react"
import {
  FieldTransferCard,
  OVERRIDE_REASONS,
} from "@/components/portal-transfer/field-transfer-card"
import {
  COVERAGE_STATEMENT,
  CLIPBOARD_PRIVACY_NOTE,
  UNSUPPORTED_AREAS,
  assembleChapterText,
  assembleFullDraftText,
  fieldWarnings,
  groupBySection,
  type WarningCode,
} from "@/lib/portal-transfer"
import { fieldReadinessRows, readinessSummary } from "@/lib/export-view"
import { copyPlain } from "@/lib/clipboard"
import {
  FieldError,
  recordCopyEvent,
  type OverrideReasonCode,
  type PortalFieldDraftDto,
} from "@/lib/fields"
import { fieldModeLabel, type PortalFieldInfoDto } from "@/lib/portal-fields"
import { SECTION_LABELS, SECTION_ORDER } from "@/lib/portal-transfer"
import { Button } from "@/components/ui/button"
import type { ReviewPackageDto } from "@/lib/review"

const PAGE_DISCLAIMER =
  "Diese Ansicht erleichtert die manuelle, feldweise Übernahme nach Innolink. " +
  "Es wird nichts automatisch übertragen oder eingereicht."

// Shared warning summary shown once above the cards instead of repeating the
// same sentences on every card.
const WARNING_SUMMARY_LABELS: Record<WarningCode, (n: number) => string> = {
  open: (n) => `${n} ${n === 1 ? "Feld enthält" : "Felder enthalten"} noch offene Angaben`,
  limit: (n) =>
    `${n} ${n === 1 ? "Feld überschreitet" : "Felder überschreiten"} das Innolink-Zeichenlimit`,
  review: (n) =>
    `Die Prüfungs-Freigabe ist nicht aktuell (betrifft ${n} ${n === 1 ? "Feld" : "Felder"})`,
}

export function PortalTransfer({
  fields,
  review,
  mockMode = false,
  confidentialReminder = false,
  embedded = false,
  runId = null,
  copyEventsEnabled = false,
  portalFields = null,
  onReload,
}: {
  fields: PortalFieldDraftDto[]
  review: ReviewPackageDto | null
  mockMode?: boolean
  confidentialReminder?: boolean
  /** When rendered inside the Export screen, the page header is provided there. */
  embedded?: boolean
  /** Slice 3: with runId + copyEventsEnabled each copy records a server-side
   * CopyEvent (fail-open). Absent in mock mode → today's behavior. */
  runId?: string | null
  copyEventsEnabled?: boolean
  /** Slice 4: full registry catalog. When present, a toggle offers the
   * read-only "Alle Portalfelder" checklist; absent → today's view only. */
  portalFields?: PortalFieldInfoDto[] | null
  /** Reload the field list after a stale-version conflict (409). */
  onReload?: () => void
}) {
  // Copy log per field. The timestamp comes from the server CopyEvent when
  // available; the session-only fallback covers the fail-open path.
  const [copiedAt, setCopiedAt] = React.useState<Map<string, Date>>(new Map())
  const markCopied = React.useCallback((fieldId: string, at?: Date) => {
    setCopiedAt((prev) => new Map(prev).set(fieldId, at ?? new Date()))
  }, [])
  // Slice 4: "Unterstützte Felder" (default, today's view) vs "Alle Portalfelder".
  const [showAllFields, setShowAllFields] = React.useState(false)
  const hasCatalog = (portalFields?.length ?? 0) > 0

  const groups = groupBySection(fields)
  const readinessRows = fieldReadinessRows(fields, review)

  // Aggregate identical warnings once, instead of repeating them per card.
  const warningCounts = new Map<WarningCode, number>()
  for (const field of fields) {
    for (const w of fieldWarnings(field, review)) {
      warningCounts.set(w.code, (warningCounts.get(w.code) ?? 0) + 1)
    }
  }

  return (
    <div className={embedded ? "flex flex-col gap-5" : "mx-auto flex max-w-4xl flex-col gap-5"}>
      {!embedded && (
        <div>
          <h1 className="text-lg font-semibold">Innolink-Kopieransicht</h1>
          <p className="text-sm text-muted-foreground">{PAGE_DISCLAIMER}</p>
        </div>
      )}

      {/* Generic clipboard privacy reminder — always shown (never relies solely
          on local intake state). */}
      <p className="flex items-start gap-2 rounded-md border border-border bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
        <Info className="mt-0.5 size-4 shrink-0" />
        <span>
          {CLIPBOARD_PRIVACY_NOTE}
          {confidentialReminder &&
            " Dieses Projekt ist als vertraulich gekennzeichnet — bitte besonders sorgfältig mit kopierten Inhalten umgehen."}
        </span>
      </p>

      {mockMode && (
        <p className="text-xs text-muted-foreground">
          Hinweis: Der Prüfungs-Status ist in der Demo-Ansicht nicht verfügbar.
        </p>
      )}

      {/* Slice 4: view toggle — default stays today's supported-fields view. */}
      {hasCatalog && (
        <div className="flex items-center gap-2" role="group" aria-label="Feldansicht">
          <Button
            type="button"
            size="sm"
            variant={showAllFields ? "outline" : "default"}
            aria-pressed={!showAllFields}
            onClick={() => setShowAllFields(false)}
          >
            Unterstützte Felder
          </Button>
          <Button
            type="button"
            size="sm"
            variant={showAllFields ? "default" : "outline"}
            aria-pressed={showAllFields}
            onClick={() => setShowAllFields(true)}
          >
            Alle Portalfelder
          </Button>
        </div>
      )}

      {/* Copy progress + shared warning summary (work progress, no funding statement). */}
      {fields.length > 0 && (
        <div className="flex flex-col gap-2">
          <p className="text-sm text-foreground" data-testid="copy-progress">
            {readinessSummary(readinessRows)}{" "}
            <span className="text-muted-foreground">
              {copiedAt.size} {copiedAt.size === 1 ? "Feld" : "Felder"} in dieser
              Sitzung kopiert.
            </span>
          </p>
          {warningCounts.size > 0 && (
            <div
              role="status"
              className="flex items-start gap-2 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-900"
            >
              <AlertTriangle className="mt-0.5 size-3.5 shrink-0" />
              <span>
                {[...warningCounts.entries()]
                  .map(([code, n]) => WARNING_SUMMARY_LABELS[code](n))
                  .join(" · ")}
                . Details stehen an den betroffenen Feldern.
              </span>
            </div>
          )}
        </div>
      )}

      {fields.length === 0 ? (
        <p className="rounded-md border border-dashed border-border bg-muted/30 px-4 py-10 text-center text-sm text-muted-foreground">
          Für diesen Lauf liegen noch keine übernehmbaren Feldtexte vor.
        </p>
      ) : (
        <>
          {/* R6: Gesamtentwurf als Arbeitskopie kopieren (mit Feldüberschriften). */}
          <BulkCopyButton
            label="Gesamten Textentwurf kopieren"
            fields={fields}
            review={review}
            copyText={assembleFullDraftText(fields)}
            runId={mockMode ? null : runId}
            copyEventsEnabled={copyEventsEnabled}
            onCopied={markCopied}
            onReload={onReload}
          />
          {groups.map((group) => (
            <section key={group.key} className="flex flex-col gap-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h2 className="text-sm font-semibold text-muted-foreground">
                  {group.label}
                </h2>
                <BulkCopyButton
                  label="Kapitel kopieren"
                  fields={group.fields}
                  review={review}
                  copyText={assembleChapterText(group)}
                  runId={mockMode ? null : runId}
                  copyEventsEnabled={copyEventsEnabled}
                  onCopied={markCopied}
                  onReload={onReload}
                />
              </div>
              {group.fields.map((field) => (
                <FieldTransferCard
                  key={field.field_id}
                  field={field}
                  review={review}
                  copiedAt={copiedAt.get(field.field_id) ?? null}
                  onCopied={markCopied}
                  runId={mockMode ? null : runId}
                  copyEventsEnabled={copyEventsEnabled}
                  subsections={
                    portalFields?.find((p) => p.field_id === field.field_id)
                      ?.subsections ?? []
                  }
                  onReload={onReload}
                />
              ))}
            </section>
          ))}
        </>
      )}

      {/* Slice 4: read-only checklist of the portal fields the Beta does not
          draft — grouped by portal section incl. Summary & Submit. */}
      {hasCatalog && showAllFields && (
        <ManualPortalChecklist portalFields={portalFields ?? []} />
      )}

      {/* Mandatory coverage panel — always rendered. */}
      <section className="flex flex-col gap-3 rounded-lg border border-border bg-card p-4">
        <h2 className="text-sm font-semibold">Abdeckung der Übernahmeansicht</h2>
        <p className="text-xs text-muted-foreground">{COVERAGE_STATEMENT}</p>
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            {/* "Unterstützt" heisst: die Beta kennt das Feld — nicht, dass der
                Text bereits kopierbereit ist (siehe Fortschritt oben). */}
            <h3 className="text-xs font-semibold">Von der Beta unterstützte Felder</h3>
            <ul className="mt-1 flex flex-col gap-0.5 text-xs text-muted-foreground">
              {fields.length === 0 ? (
                <li>Keine unterstützten Feldtexte vorhanden.</li>
              ) : (
                fields.map((f) => <li key={f.field_id}>• {f.field_name}</li>)
              )}
            </ul>
          </div>
          <div>
            <h3 className="text-xs font-semibold">
              Noch direkt in Innolink zu erfassen
            </h3>
            <ul className="mt-1 flex flex-col gap-0.5 text-xs text-muted-foreground">
              {UNSUPPORTED_AREAS.map((area) => (
                <li key={area}>• {area}</li>
              ))}
            </ul>
          </div>
        </div>
      </section>
    </div>
  )
}

/**
 * R6 Kapitel-/Gesamt-Kopie: kopiert die Arbeitskopie mehrerer Felder in einem
 * Schritt. Je enthaltenem Feld wird ein metadata-only CopyEvent protokolliert
 * (bestehende API, kein Rohtext); Felder mit Hinweisen verlangen wie bei der
 * Einzelkopie eine dokumentierte Begründung. Nie "einreichbereit".
 */
function BulkCopyButton({
  label,
  fields,
  review,
  copyText,
  runId = null,
  copyEventsEnabled = false,
  onCopied,
  onReload,
}: Readonly<{
  label: string
  fields: PortalFieldDraftDto[]
  review: ReviewPackageDto | null
  copyText: string
  runId?: string | null
  copyEventsEnabled?: boolean
  onCopied: (fieldId: string, at?: Date) => void
  onReload?: () => void
}>) {
  const [confirming, setConfirming] = React.useState(false)
  const [reasonCode, setReasonCode] = React.useState<OverrideReasonCode | null>(null)
  const [reasonNote, setReasonNote] = React.useState("")
  const [message, setMessage] = React.useState<string | null>(null)

  const warningsByField = fields.map(
    (field) => [field, fieldWarnings(field, review)] as const
  )
  const warnedCount = warningsByField.filter(([, w]) => w.length > 0).length
  const loggingActive = Boolean(runId) && copyEventsEnabled
  const needsReason = loggingActive && warnedCount > 0
  const reasonMissing =
    needsReason &&
    (reasonCode === null || (reasonCode === "other" && reasonNote.trim() === ""))

  async function copyAll() {
    setMessage(null)
    if (loggingActive && runId) {
      const results = await Promise.allSettled(
        warningsByField.map(([field, warnings]) =>
          recordCopyEvent(runId, field.field_id, {
            draft_version_id: field.current_version.draft_version_id,
            client_warnings: warnings.map((w) => w.code),
            ...(warnings.length > 0 && reasonCode
              ? {
                  override_reason_code: reasonCode,
                  ...(reasonCode === "other"
                    ? { override_reason_note: reasonNote.trim() }
                    : {}),
                }
              : {}),
          })
        )
      )
      const stale = results.some(
        (r) =>
          r.status === "rejected" &&
          r.reason instanceof FieldError &&
          r.reason.status === 409
      )
      if (stale) {
        // Angezeigter Stand ist veraltet — nicht kopieren, neu laden.
        setConfirming(false)
        setMessage(
          "Mindestens ein Feldtext wurde zwischenzeitlich geändert und wird neu geladen."
        )
        onReload?.()
        return
      }
      if (results.some((r) => r.status === "rejected")) {
        // Fail-open wie bei der Einzelkopie: Logging blockiert das Kopieren nie.
        setMessage("Übernahme konnte nicht vollständig protokolliert werden.")
      }
    }
    setConfirming(false)
    setReasonCode(null)
    setReasonNote("")
    try {
      await copyPlain(copyText)
      const now = new Date()
      for (const field of fields) onCopied(field.field_id, now)
    } catch {
      setMessage(
        "Automatisches Kopieren ist nicht möglich. Bitte kopieren Sie die Felder einzeln."
      )
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <Button
        type="button"
        size="sm"
        variant="outline"
        onClick={() => (warnedCount > 0 ? setConfirming(true) : void copyAll())}
      >
        <Copy data-icon="inline-start" />
        {label}
      </Button>
      {confirming && (
        <div className="flex flex-col gap-2 rounded border border-amber-300 bg-amber-50 px-2 py-2 text-xs text-amber-900">
          <span>
            {warnedCount} {warnedCount === 1 ? "Feld enthält" : "Felder enthalten"}{" "}
            noch Hinweise. Sie kopieren eine Arbeitskopie — keine geprüfte
            Endfassung.
          </span>
          {needsReason && (
            <fieldset className="flex flex-col gap-1">
              <legend className="font-semibold">
                Grund für Übernahme trotz Hinweisen
              </legend>
              {OVERRIDE_REASONS.map((reason) => (
                <label key={reason.code} className="flex items-center gap-2">
                  <input
                    type="radio"
                    name={`bulk-copy-reason-${label}`}
                    checked={reasonCode === reason.code}
                    onChange={() => setReasonCode(reason.code)}
                  />
                  {reason.label}
                </label>
              ))}
              {reasonCode === "other" && (
                <input
                  type="text"
                  value={reasonNote}
                  onChange={(e) => setReasonNote(e.target.value)}
                  maxLength={200}
                  placeholder="Kurze Begründung"
                  aria-label="Kurze Begründung"
                  className="rounded border border-amber-300 bg-white px-2 py-1 text-xs text-foreground"
                />
              )}
            </fieldset>
          )}
          <div className="flex flex-wrap items-center gap-2">
            <Button size="sm" disabled={reasonMissing} onClick={() => void copyAll()}>
              Trotzdem kopieren
            </Button>
            <Button size="sm" variant="outline" onClick={() => setConfirming(false)}>
              Abbrechen
            </Button>
          </div>
        </div>
      )}
      {message && (
        <p role="status" className="text-xs text-amber-900">
          {message}
        </p>
      )}
    </div>
  )
}

/** Slice 4: read-only checklist "Im Portal manuell erfassen" — all registry
 * fields WITHOUT an active draft, grouped by portal section (incl. SUM).
 * No check-off state, no persistence. */
function ManualPortalChecklist({
  portalFields,
}: Readonly<{ portalFields: PortalFieldInfoDto[] }>) {
  const manual = portalFields.filter((f) => !f.draft_available)
  const sections = [...SECTION_ORDER].filter((key) =>
    manual.some((f) => f.section === key)
  )
  return (
    <section
      aria-label="Im Portal manuell erfassen"
      className="flex flex-col gap-4 rounded-lg border border-border bg-card p-4"
    >
      <div>
        <h2 className="text-sm font-semibold">Im Portal manuell erfassen</h2>
        <p className="text-xs text-muted-foreground">
          Diese Portalfelder bereitet die Beta nicht als Textentwurf vor — sie
          werden direkt in Innolink erfasst, hochgeladen oder beachtet.
        </p>
      </div>
      {sections.map((key) => (
        <div key={key} className="flex flex-col gap-1.5">
          <h3 className="text-xs font-semibold text-muted-foreground">
            {SECTION_LABELS[key] ?? "Weitere"}
          </h3>
          <ul className="flex flex-col gap-1">
            {manual
              .filter((f) => f.section === key)
              .map((f) => (
                <li
                  key={f.field_id}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-border/70 bg-background px-3 py-1.5"
                >
                  <span className="text-xs text-foreground">{f.label}</span>
                  <span className="flex items-center gap-2">
                    {f.character_limit != null && (
                      <span className="text-[11px] text-muted-foreground">
                        max. {f.character_limit.toLocaleString("de-CH")} Zeichen
                      </span>
                    )}
                    <span className="inline-flex items-center rounded-full border border-border bg-muted/40 px-2 py-0.5 text-[11px] text-muted-foreground">
                      {fieldModeLabel(f)}
                    </span>
                  </span>
                </li>
              ))}
          </ul>
        </div>
      ))}
    </section>
  )
}
