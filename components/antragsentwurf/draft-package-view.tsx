"use client"

// DEMO.1 — Antragsentwurf view: shows one fake/demo DraftPackage (8 fields)
// with per-field draft text, status, missing inputs, copy buttons and a
// collapsed technical-details section. Human review is always required;
// nothing here submits or approves anything.

import * as React from "react"
import { ClipboardCopy, Copy, RefreshCw, Sparkles } from "lucide-react"
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { copyPlain } from "@/lib/clipboard"
import {
  generateDemoDraft,
  IntegratedDraftError,
  type DraftPackageDto,
  type FieldDraftItemDto,
} from "@/lib/integrated-draft"
import {
  buildWorkingDraftText,
  costStatusLabel,
  fieldLabel,
  FIELD_DRAFT_STATUS_STYLE,
  fieldDraftStatusLabel,
  researchHint,
  summarizeFields,
} from "@/lib/integrated-draft-view"
import { cn } from "@/lib/utils"

const HUMAN_REVIEW_HINT =
  "Dieser Demo-Entwurf wurde durch einen Demo-Generator und deterministische Prüfungen " +
  "vorbereitet. Er ist nicht automatisch einreichungsbereit und benötigt Human Review."
const COPY_WARNING = "Copy-Paste ist Arbeitsentwurf, keine finale Freigabe."
const QUALITY_HINT = "Qualitätsbewertung durch Reviewer ausstehend."
const RESEARCH_NOTE = "Research-Kandidaten sind keine bestätigten Fakten."

function num(value: number | null): string {
  return value === null || value === undefined ? "—" : String(value)
}

function SummaryCard({ label, value }: Readonly<{ label: string; value: string }>) {
  return (
    <div className="rounded-lg border border-border bg-card px-4 py-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 text-lg font-semibold">{value}</p>
    </div>
  )
}

function FieldCard({
  field,
  pkg,
}: Readonly<{ field: FieldDraftItemDto; pkg: DraftPackageDto }>) {
  const [copied, setCopied] = React.useState(false)
  const hint = researchHint(pkg, field.field_id)
  const hasModelCall = field.generation_kind === "model_generated"

  async function copyField() {
    if (!field.suggestion_text) return
    try {
      await copyPlain(field.suggestion_text)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 2500)
    } catch {
      /* clipboard unavailable — button stays, nothing else breaks */
    }
  }

  return (
    <Card data-testid={`draft-field-${field.field_id}`}>
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center gap-2 text-base">
          {fieldLabel(field)}
          <Badge className={cn(FIELD_DRAFT_STATUS_STYLE[field.status])}>
            {fieldDraftStatusLabel(field)}
          </Badge>
          {field.human_review_required && (
            <Badge variant="outline">Prüfung nötig</Badge>
          )}
        </CardTitle>
        {hint && (
          <CardDescription>
            {hint.label}: {hint.used ? "ja" : "nein"} — {RESEARCH_NOTE}
          </CardDescription>
        )}
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {field.suggestion_text ? (
          <div className="max-h-56 overflow-y-auto whitespace-pre-wrap rounded-md bg-muted/40 p-3 text-sm">
            {field.suggestion_text}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">
            Für dieses Feld liegt noch kein Entwurfstext vor.
          </p>
        )}

        {field.missing_inputs.length > 0 && (
          <div>
            <p className="text-sm font-medium">Fehlende Angaben</p>
            <ul className="mt-1 list-disc pl-5 text-sm text-muted-foreground">
              {field.missing_inputs.map((mi) => (
                <li key={mi.label}>{mi.label}</li>
              ))}
            </ul>
          </div>
        )}

        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={copyField}
            disabled={!field.suggestion_text}
          >
            <Copy data-icon="inline-start" />
            Text kopieren
          </Button>
          {copied && <Badge variant="secondary">Kopiert</Badge>}
        </div>

        <Accordion>
          <AccordionItem value="technische-details">
            <AccordionTrigger>Technische Details</AccordionTrigger>
            <AccordionContent>
              <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
                <dt className="text-muted-foreground">Feld-ID</dt>
                <dd>
                  <code className="rounded bg-muted px-1.5 py-0.5">{field.field_id}</code>
                </dd>
                <dt className="text-muted-foreground">Provider</dt>
                <dd>
                  {field.generation_kind === "fake_demo"
                    ? "Demo-Generator – kein Modellaufruf"
                    : (hasModelCall ? field.provider : null) ?? "Kein Modellaufruf"}
                </dd>
                <dt className="text-muted-foreground">Modell</dt>
                <dd>{hasModelCall ? (field.model ?? "—") : "Kein Modellaufruf"}</dd>
                <dt className="text-muted-foreground">Tokens (in/out/total)</dt>
                <dd>
                  {hasModelCall
                    ? `${num(field.input_tokens)}/${num(field.output_tokens)}/${num(field.total_tokens)}`
                    : "—"}
                </dd>
                <dt className="text-muted-foreground">Latenz (ms)</dt>
                <dd>{hasModelCall ? num(field.latency_ms) : "—"}</dd>
                <dt className="text-muted-foreground">Kostenstatus</dt>
                <dd>{costStatusLabel(field.cost_status)}</dd>
              </dl>
            </AccordionContent>
          </AccordionItem>
        </Accordion>
      </CardContent>
    </Card>
  )
}

export function DraftPackageView() {
  const [pkg, setPkg] = React.useState<DraftPackageDto | null>(null)
  const [loading, setLoading] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const [copiedAll, setCopiedAll] = React.useState(false)

  function generate() {
    setLoading(true)
    setError(null)
    generateDemoDraft()
      .then(setPkg)
      .catch((e) =>
        setError(
          e instanceof IntegratedDraftError
            ? e.message
            : "Der Antragsentwurf konnte nicht erstellt werden."
        )
      )
      .finally(() => setLoading(false))
  }

  async function copyAll() {
    if (!pkg) return
    try {
      await copyPlain(buildWorkingDraftText(pkg))
      setCopiedAll(true)
      window.setTimeout(() => setCopiedAll(false), 2500)
    } catch {
      /* clipboard unavailable */
    }
  }

  const summary = pkg ? summarizeFields(pkg.fields) : null

  return (
    <section className="flex flex-col gap-6" data-testid="draft-package-view">
      <div>
        <h1 className="text-xl font-semibold">Demo-Antragsentwurf</h1>
        <p className="mt-1 max-w-3xl text-sm text-muted-foreground">{HUMAN_REVIEW_HINT}</p>
      </div>

      {!pkg && !loading && !error && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Demo-Entwurf erstellen</CardTitle>
            <CardDescription>
              Erzeugt einen synthetischen Antragsentwurf für die 8 unterstützten
              Innolink-Felder (Demo-Modus, keine echten KI-Calls).
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button onClick={generate}>
              <Sparkles data-icon="inline-start" />
              Antragsentwurf erstellen (Demo)
            </Button>
          </CardContent>
        </Card>
      )}

      {loading && (
        <div className="flex flex-col gap-4">
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            {[0, 1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-20 rounded-lg" />
            ))}
          </div>
          <Skeleton className="h-48 rounded-lg" />
        </div>
      )}

      {error && (
        <div className="flex flex-col items-center gap-4 rounded-lg border border-dashed border-border bg-muted/30 px-6 py-12 text-center">
          <p className="text-sm text-muted-foreground">{error}</p>
          <Button variant="outline" onClick={generate}>
            <RefreshCw data-icon="inline-start" />
            Erneut versuchen
          </Button>
        </div>
      )}

      {pkg && summary && (
        <>
          <div
            className="grid grid-cols-2 gap-4 md:grid-cols-4"
            data-testid="draft-summary"
          >
            <SummaryCard label="Felder gesamt" value={String(summary.total)} />
            <SummaryCard label="Demo-Vorschlag erstellt" value={String(summary.generated)} />
            <SummaryCard
              label="Automatisch übernommen"
              value={String(summary.deterministic)}
            />
            <SummaryCard label="Angaben fehlen" value={String(summary.missingInputs)} />
            <SummaryCard label="Fehlgeschlagen" value={String(summary.failed)} />
            <SummaryCard
              label="Tokens gesamt"
              value={String(pkg.usage_summary.total_tokens)}
            />
            <SummaryCard
              label="Kostenstatus"
              value={Object.keys(pkg.usage_summary.cost_status_counts)
                .map(costStatusLabel)
                .join(", ") || "—"}
            />
            <SummaryCard label="Provider-Modus" value="Fake/Demo" />
          </div>

          <p className="text-sm text-muted-foreground">{QUALITY_HINT}</p>

          <div className="flex flex-wrap items-center gap-3">
            <Button variant="outline" onClick={copyAll}>
              <ClipboardCopy data-icon="inline-start" />
              Gesamten Entwurf kopieren
            </Button>
            {copiedAll && <Badge variant="secondary">Kopiert</Badge>}
            <p className="text-xs text-muted-foreground">{COPY_WARNING}</p>
          </div>

          <div className="flex flex-col gap-4">
            {pkg.fields.map((field) => (
              <FieldCard key={field.field_id} field={field} pkg={pkg} />
            ))}
          </div>
        </>
      )}
    </section>
  )
}
