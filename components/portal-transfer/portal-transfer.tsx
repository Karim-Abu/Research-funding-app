"use client"

import * as React from "react"
import { Info } from "lucide-react"
import { FieldTransferCard } from "@/components/portal-transfer/field-transfer-card"
import {
  COVERAGE_STATEMENT,
  CLIPBOARD_PRIVACY_NOTE,
  UNSUPPORTED_AREAS,
  groupBySection,
} from "@/lib/portal-transfer"
import type { PortalFieldDraftDto } from "@/lib/fields"
import type { ReviewPackageDto } from "@/lib/review"

const PAGE_DISCLAIMER =
  "Diese Ansicht erleichtert die manuelle, feldweise Übernahme nach Innolink. " +
  "Es wird nichts automatisch übertragen oder eingereicht."

export function PortalTransfer({
  fields,
  review,
  mockMode = false,
  confidentialReminder = false,
}: {
  fields: PortalFieldDraftDto[]
  review: ReviewPackageDto | null
  mockMode?: boolean
  confidentialReminder?: boolean
}) {
  const [copied, setCopied] = React.useState<Set<string>>(new Set())
  const markCopied = React.useCallback((fieldId: string) => {
    setCopied((prev) => new Set(prev).add(fieldId))
  }, [])

  const groups = groupBySection(fields)

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-5">
      <div>
        <h1 className="text-lg font-semibold">Innolink-Übernahme</h1>
        <p className="text-sm text-muted-foreground">{PAGE_DISCLAIMER}</p>
      </div>

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
          Hinweis: Review-Status ist in der Demo-Ansicht nicht verfügbar.
        </p>
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
                copied={copied.has(field.field_id)}
                onCopied={markCopied}
              />
            ))}
          </section>
        ))
      )}

      {/* Mandatory coverage panel — always rendered. */}
      <section className="flex flex-col gap-3 rounded-lg border border-border bg-card p-4">
        <h2 className="text-sm font-semibold">Abdeckung der Übernahmeansicht</h2>
        <p className="text-xs text-muted-foreground">{COVERAGE_STATEMENT}</p>
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <h3 className="text-xs font-semibold">Bereit für die feldweise Übernahme</h3>
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
