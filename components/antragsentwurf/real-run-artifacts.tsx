"use client"

// DEMO.1 — read-only view over already generated R5.9-REAL artifacts. Shows
// per provider the whitelist report data (status, tokens, latency, cost
// status, 200-char preview). Never triggers a new provider call; without
// artifacts it shows a friendly empty state (no error).

import * as React from "react"
import { Badge } from "@/components/ui/badge"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import {
  getRealRunArtifacts,
  type RealRunReportDto,
} from "@/lib/integrated-draft"
import { costStatusLabel } from "@/lib/integrated-draft-view"

const NO_NEW_CALLS_HINT =
  "Diese Ansicht zeigt bereits erzeugte Evaluationsartefakte. Es werden keine " +
  "neuen Provider-Calls ausgeführt."
const EMPTY_STATE =
  "Noch kein Real-Provider-Lauf vorhanden. Führe den manuellen R5.9-REAL-Runner aus."
const PREVIEW_NOTE =
  "Feldtexte werden hier nur als Kurzvorschau (max. 200 Zeichen) gezeigt; " +
  "vollständige Texte liegen im normalen Entwurfs- und Report-Fluss."

function num(value: number | null): string {
  return value === null || value === undefined ? "—" : String(value)
}

function ProviderCard({
  provider,
  report,
}: Readonly<{ provider: string; report: RealRunReportDto }>) {
  return (
    <Card data-testid={`real-run-${provider}`}>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          Provider: {provider}
          <Badge variant="outline">{report.data_mode}</Badge>
        </CardTitle>
        <CardDescription>
          Tokens gesamt: {report.usage_summary.total_tokens} · Kostenstatus:{" "}
          {Object.keys(report.usage_summary.cost_status_counts)
            .map(costStatusLabel)
            .join(", ") || "—"}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-border text-muted-foreground">
                <th className="py-1.5 pr-3 font-medium">Feld</th>
                <th className="py-1.5 pr-3 font-medium">Status</th>
                <th className="py-1.5 pr-3 font-medium">Modell</th>
                <th className="py-1.5 pr-3 font-medium">Tokens in/out/total</th>
                <th className="py-1.5 pr-3 font-medium">Latenz (ms)</th>
                <th className="py-1.5 pr-3 font-medium">Kostenstatus</th>
                <th className="py-1.5 pr-3 font-medium">Fehlende Angaben</th>
                <th className="py-1.5 font-medium">Prüfung nötig</th>
              </tr>
            </thead>
            <tbody>
              {report.fields.map((f) => (
                <tr key={f.field_id} className="border-b border-border/50 align-top">
                  <td className="py-1.5 pr-3">
                    <code className="rounded bg-muted px-1 py-0.5">{f.field_id}</code>
                    <p className="mt-1 max-w-xs text-muted-foreground">
                      {f.suggestion_preview}
                    </p>
                  </td>
                  <td className="py-1.5 pr-3">{f.status}</td>
                  <td className="py-1.5 pr-3">{f.model ?? "—"}</td>
                  <td className="py-1.5 pr-3">
                    {num(f.input_tokens)}/{num(f.output_tokens)}/{num(f.total_tokens)}
                  </td>
                  <td className="py-1.5 pr-3">{num(f.latency_ms)}</td>
                  <td className="py-1.5 pr-3">{costStatusLabel(f.cost_status)}</td>
                  <td className="py-1.5 pr-3">{f.missing_inputs_count}</td>
                  <td className="py-1.5">{f.human_review_required ? "ja" : "nein"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-3 text-xs text-muted-foreground">{PREVIEW_NOTE}</p>
      </CardContent>
    </Card>
  )
}

export function RealRunArtifacts() {
  const [providers, setProviders] = React.useState<Record<
    string,
    RealRunReportDto
  > | null>(null)
  const [loaded, setLoaded] = React.useState(false)

  React.useEffect(() => {
    getRealRunArtifacts()
      .then((data) => setProviders(data.providers))
      .catch(() => setProviders({}))
      .finally(() => setLoaded(true))
  }, [])

  return (
    <section className="flex flex-col gap-4" data-testid="real-run-artifacts">
      <div>
        <h2 className="text-lg font-semibold">Realer Provider-Test</h2>
        <p className="mt-1 max-w-3xl text-sm text-muted-foreground">{NO_NEW_CALLS_HINT}</p>
      </div>
      {!loaded && <Skeleton className="h-32 rounded-lg" />}
      {loaded && providers && Object.keys(providers).length === 0 && (
        <div className="rounded-lg border border-dashed border-border bg-muted/30 px-6 py-10 text-center">
          <p className="text-sm text-muted-foreground">{EMPTY_STATE}</p>
        </div>
      )}
      {loaded &&
        providers &&
        Object.entries(providers).map(([provider, report]) => (
          <ProviderCard key={provider} provider={provider} report={report} />
        ))}
    </section>
  )
}
