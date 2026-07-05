"use client"

import * as React from "react"
import { AlertTriangle, Info } from "lucide-react"
import { FieldTransferCard } from "@/components/portal-transfer/field-transfer-card"
import {
  COVERAGE_STATEMENT,
  CLIPBOARD_PRIVACY_NOTE,
  UNSUPPORTED_AREAS,
  fieldWarnings,
  groupBySection,
  type WarningCode,
} from "@/lib/portal-transfer"
import { fieldReadinessRows, readinessSummary } from "@/lib/export-view"
import type { PortalFieldDraftDto } from "@/lib/fields"
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
        groups.map((group) => (
          <section key={group.key} className="flex flex-col gap-3">
            <h2 className="text-sm font-semibold text-muted-foreground">{group.label}</h2>
            {group.fields.map((field) => (
              <FieldTransferCard
                key={field.field_id}
                field={field}
                review={review}
                copiedAt={copiedAt.get(field.field_id) ?? null}
                onCopied={markCopied}
                runId={mockMode ? null : runId}
                copyEventsEnabled={copyEventsEnabled}
                onReload={onReload}
              />
            ))}
          </section>
        ))
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
