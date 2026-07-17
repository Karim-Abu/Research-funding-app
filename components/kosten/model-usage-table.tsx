import {
  aggregateProviderModels,
  formatCost,
  formatDuration,
  type KostenRunViewModel,
  type ProviderModelAggregate,
} from "@/lib/kosten"

function formatSuccessRate(value: number | undefined): string {
  return value === undefined ? "Nicht verfügbar" : `${Math.round(value)} %`
}

function UsageCard({ aggregate }: { aggregate: ProviderModelAggregate }) {
  return (
    <li className="rounded-lg border border-border bg-card p-4">
      <p className="text-sm font-semibold text-foreground">{aggregate.provider}</p>
      <p className="text-xs text-muted-foreground">{aggregate.model}</p>
      <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
        <div>
          <dt className="text-xs text-muted-foreground">Einsätze</dt>
          <dd className="mt-0.5 font-medium tabular-nums">
            {aggregate.usageCount ?? "Nicht verfügbar"}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-muted-foreground">Ø Latenz je Aufruf</dt>
          <dd className="mt-0.5 font-medium tabular-nums">
            {formatDuration(aggregate.averageLatencyMs)}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-muted-foreground">Ø Kosten</dt>
          <dd className="mt-0.5 font-medium tabular-nums">
            {formatCost(aggregate.averageCost)}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-muted-foreground">Gesamtkosten</dt>
          <dd className="mt-0.5 font-medium tabular-nums">
            {formatCost(aggregate.totalCost)}
          </dd>
        </div>
        <div className="col-span-2">
          <dt className="text-xs text-muted-foreground">Technisch erfolgreich</dt>
          <dd className="mt-0.5 font-medium tabular-nums">
            {formatSuccessRate(aggregate.technicalSuccessRate)}
          </dd>
        </div>
      </dl>
    </li>
  )
}

export function ModelUsageTable({ runs }: { runs: readonly KostenRunViewModel[] }) {
  const aggregates = aggregateProviderModels(runs)

  return (
    <section aria-labelledby="models-heading">
      <div>
        <h2 id="models-heading" className="text-lg font-semibold text-foreground">
          Modelle &amp; Provider
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Gemeldete Nutzung, Kosten und technische Laufzeiten nach Dienst und Modell.
        </p>
      </div>

      {aggregates.length === 0 ? (
        <div className="mt-4 rounded-lg border border-dashed border-border bg-card px-6 py-8 text-center">
          <p className="text-sm text-muted-foreground">
            Keine Modell- oder Providerdaten verfügbar.
          </p>
        </div>
      ) : (
        <>
          <div className="mt-4 hidden overflow-x-auto rounded-lg border border-border bg-card lg:block">
            <table className="w-full min-w-[820px] text-sm" aria-label="Modell- und Provider-Nutzung">
              <thead>
                <tr className="border-b border-border bg-muted/25 text-left text-xs text-muted-foreground">
                  <th scope="col" className="px-4 py-3 font-medium">Provider / Modell</th>
                  <th scope="col" className="px-4 py-3 text-right font-medium">Einsätze</th>
                  <th scope="col" className="px-4 py-3 text-right font-medium">Ø Latenz je Aufruf</th>
                  <th scope="col" className="px-4 py-3 text-right font-medium">Ø Kosten</th>
                  <th scope="col" className="px-4 py-3 text-right font-medium">Gesamtkosten</th>
                  <th scope="col" className="px-4 py-3 text-right font-medium">Technisch erfolgreich</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {aggregates.map((aggregate) => (
                  <tr key={aggregate.id}>
                    <td className="px-4 py-3">
                      <span className="font-medium text-foreground">{aggregate.provider}</span>
                      <span className="block text-xs text-muted-foreground">{aggregate.model}</span>
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums">{aggregate.usageCount ?? "Nicht verfügbar"}</td>
                    <td className="px-4 py-3 text-right tabular-nums">{formatDuration(aggregate.averageLatencyMs)}</td>
                    <td className="px-4 py-3 text-right tabular-nums">{formatCost(aggregate.averageCost)}</td>
                    <td className="px-4 py-3 text-right tabular-nums">{formatCost(aggregate.totalCost)}</td>
                    <td className="px-4 py-3 text-right tabular-nums">{formatSuccessRate(aggregate.technicalSuccessRate)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <ul className="mt-4 flex flex-col gap-3 lg:hidden">
            {aggregates.map((aggregate) => (
              <UsageCard key={aggregate.id} aggregate={aggregate} />
            ))}
          </ul>
        </>
      )}

      <p className="mt-3 text-xs leading-relaxed text-muted-foreground">
        Kosten, Geschwindigkeit und technischer Abschluss beschreiben die Ausführung.
        Sie sind keine Bewertung der inhaltlichen Qualität eines Modells.
      </p>
    </section>
  )
}
