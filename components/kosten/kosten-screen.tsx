"use client"

import * as React from "react"
import {
  Check,
  CheckCircle2,
  CircleDollarSign,
  Info,
  OctagonX,
  Pencil,
  Timer,
  WalletCards,
  X,
  XCircle,
} from "lucide-react"
import { ModelUsageTable } from "@/components/kosten/model-usage-table"
import { RunsTable } from "@/components/kosten/runs-table"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Progress } from "@/components/ui/progress"
import { Separator } from "@/components/ui/separator"
import { RUNS, SERVICES, USAGE_LIMITS } from "@/lib/kosten-mock-data"
import {
  COST_STATUS_LABELS,
  RUN_TYPE_LABELS,
  deriveKostenOverview,
  formatCost,
  formatDateTime,
  formatDuration,
  formatRemainingBudget,
  type KostenRunViewModel,
  type KostenServiceViewModel,
  type KostenUsageLimits,
} from "@/lib/kosten"
import type { Role } from "@/lib/types"
import { cn } from "@/lib/utils"

export interface KostenScreenProps {
  role: Role
  runs?: readonly KostenRunViewModel[]
  services?: readonly KostenServiceViewModel[]
  usage?: KostenUsageLimits
}

function MetricCard({
  label,
  value,
  detail,
  icon: Icon,
}: {
  label: string
  value: string
  detail: string
  icon: React.ElementType
}) {
  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <div className="flex items-start justify-between gap-3">
        <p className="text-xs font-medium text-muted-foreground">{label}</p>
        <Icon aria-hidden className="size-4 shrink-0 text-muted-foreground" />
      </div>
      <p className="mt-3 break-words text-xl font-semibold tracking-tight text-foreground tabular-nums">
        {value}
      </p>
      <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{detail}</p>
    </div>
  )
}

function UsageSection({
  role,
  runs,
  usage,
}: {
  role: Role
  runs: readonly KostenRunViewModel[]
  usage: KostenUsageLimits
}) {
  const overview = React.useMemo(
    () => deriveKostenOverview(runs, usage.projectLimitChf),
    [runs, usage.projectLimitChf]
  )
  const percent = overview.usagePercent
  const displayedPercent = Math.min(100, Math.max(0, percent ?? 0))
  const isStopped = percent !== undefined && percent >= 100
  const isWarning = percent !== undefined && percent >= 80 && percent < 100
  const [perRunLimit, setPerRunLimit] = React.useState(usage.perRunLimitChf)
  const [limitInput, setLimitInput] = React.useState(String(usage.perRunLimitChf))
  const [editing, setEditing] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  React.useEffect(() => {
    setPerRunLimit(usage.perRunLimitChf)
    setLimitInput(String(usage.perRunLimitChf))
  }, [usage.perRunLimitChf])

  function handleApply() {
    const next = Number(limitInput)
    if (
      !Number.isFinite(next) ||
      next < usage.minPerRunLimitChf ||
      next > usage.maxPerRunLimitChf
    ) {
      setError(
        `Zulässig sind CHF ${usage.minPerRunLimitChf.toFixed(2)} bis CHF ${usage.maxPerRunLimitChf.toFixed(2)}.`
      )
      return
    }
    setPerRunLimit(next)
    setError(null)
    setEditing(false)
  }

  function handleCancel() {
    setLimitInput(String(perRunLimit))
    setError(null)
    setEditing(false)
  }

  const progressLabel =
    percent === undefined
      ? "Projektverbrauch nicht verfügbar"
      : `${overview.totalCost.status === "partial" ? "Mindestens " : overview.totalCost.status === "estimated" ? "Ungefähr " : ""}${Math.round(percent)} Prozent des Projektlimits verbraucht`

  return (
    <section aria-labelledby="usage-heading">
      <div>
        <h2 id="usage-heading" className="text-lg font-semibold text-foreground">
          Verbrauch &amp; Limits
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Bekannter Projektverbrauch und Schutzgrenzen für weitere Durchläufe.
        </p>
      </div>

      <div className="mt-4 rounded-xl border border-border bg-card p-5">
        {isStopped && (
          <div className="mb-5 flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/5 px-3 py-2.5">
            <OctagonX aria-hidden className="mt-0.5 size-4 shrink-0 text-destructive" />
            <p className="text-sm text-destructive">
              Projektlimit erreicht. Weitere Durchläufe werden durch die Schutzregel gestoppt.
            </p>
          </div>
        )}

        <div className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(250px,1fr)]">
          <div>
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <div>
                <p className="text-sm font-medium text-foreground">Projektlimit</p>
                <p className="mt-1 text-lg font-semibold tabular-nums">
                  {formatCost(overview.totalCost)} von CHF {usage.projectLimitChf.toFixed(2)}
                </p>
              </div>
              <p
                className={cn(
                  "text-sm font-semibold tabular-nums",
                  isStopped
                    ? "text-destructive"
                    : isWarning
                      ? "text-status-partial"
                      : "text-status-fulfilled"
                )}
              >
                {percent === undefined ? "Nicht verfügbar" : `${Math.round(percent)} %`}
              </p>
            </div>
            <Progress
              value={displayedPercent}
              aria-label={progressLabel}
              className={cn(
                "mt-3 gap-0 [&_[data-slot=progress-track]]:h-2.5",
                isStopped
                  ? "[&_[data-slot=progress-indicator]]:bg-destructive"
                  : isWarning
                    ? "[&_[data-slot=progress-indicator]]:bg-status-partial"
                    : "[&_[data-slot=progress-indicator]]:bg-status-fulfilled"
              )}
            />
            <div className="mt-3 flex flex-wrap gap-x-6 gap-y-1 text-xs text-muted-foreground">
              <span>
                Restbudget: <strong className="font-medium text-foreground tabular-nums">{formatRemainingBudget(overview.remainingBudget)}</strong>
              </span>
              <span>
                Bisherige Runs: <strong className="font-medium text-foreground tabular-nums">{runs.length}</strong>
              </span>
              <span>Kostenstatus: {COST_STATUS_LABELS[overview.totalCost.status]}</span>
            </div>
            {isWarning && (
              <p className="mt-3 text-xs font-medium text-status-partial">
                Mehr als 80 % des bekannten Projektlimits sind verbraucht.
              </p>
            )}
          </div>

          <div className="rounded-lg border border-border bg-muted/20 p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-sm font-medium text-foreground">Limit pro Lauf</p>
                {!editing && (
                  <p className="mt-1 text-lg font-semibold tabular-nums">
                    CHF {perRunLimit.toFixed(2)}
                  </p>
                )}
              </div>
              {role === "lead_admin" && !editing && (
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-sm"
                  aria-label="Beispiel-Limit pro Lauf bearbeiten"
                  onClick={() => setEditing(true)}
                >
                  <Pencil aria-hidden className="size-4" />
                </Button>
              )}
            </div>

            {role === "lead_admin" && editing && (
              <div className="mt-3">
                <Label htmlFor="per-run-limit">Limit pro Lauf (CHF)</Label>
                <div className="mt-1.5 flex items-center gap-2">
                  <Input
                    id="per-run-limit"
                    type="number"
                    min={usage.minPerRunLimitChf}
                    max={usage.maxPerRunLimitChf}
                    step="0.1"
                    value={limitInput}
                    onChange={(event) => {
                      setLimitInput(event.target.value)
                      setError(null)
                    }}
                    className="w-28"
                    autoFocus
                  />
                  <Button
                    type="button"
                    size="icon-sm"
                    aria-label="Beispiel-Limit übernehmen"
                    onClick={handleApply}
                  >
                    <Check aria-hidden className="size-4" />
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-sm"
                    aria-label="Bearbeitung abbrechen"
                    onClick={handleCancel}
                  >
                    <X aria-hidden className="size-4" />
                  </Button>
                </div>
                {error && <p role="alert" className="mt-2 text-xs text-destructive">{error}</p>}
              </div>
            )}

            <p className="mt-3 text-xs leading-relaxed text-muted-foreground">
              Beispielwert – Änderungen gelten nur in dieser Ansicht und werden nicht gespeichert.
            </p>
          </div>
        </div>

        <Separator className="my-5" />
        <div className="grid gap-2 text-xs text-muted-foreground sm:grid-cols-2">
          <p>Webrecherche kann zusätzliche Kosten und Laufzeit verursachen.</p>
          <p>Mehrere Modellaufrufe erhöhen den Verbrauch. Die Schutzregel bleibt aktiv.</p>
        </div>
      </div>
    </section>
  )
}

const SERVICE_TEST_LABEL: Record<KostenServiceViewModel["lastTestStatus"], string> = {
  successful: "Letzter Test erfolgreich",
  failed: "Letzter Test fehlgeschlagen",
  not_tested: "Noch nicht getestet",
}

function ServiceRow({ service }: { service: KostenServiceViewModel }) {
  const testSuccessful = service.lastTestStatus === "successful"
  const testFailed = service.lastTestStatus === "failed"
  const helpId = `service-test-help-${service.id}`

  return (
    <li className="grid gap-3 px-5 py-4 md:grid-cols-[minmax(180px,1fr)_auto_minmax(210px,0.8fr)_auto] md:items-center">
      <div>
        <p className="text-sm font-medium text-foreground">{service.name}</p>
        {service.subtitle && <p className="text-xs text-muted-foreground">{service.subtitle}</p>}
      </div>
      <Badge
        variant="outline"
        className={cn(
          "h-auto w-fit py-1",
          service.configured
            ? "border-status-fulfilled/40 bg-status-fulfilled/10 text-status-fulfilled"
            : "border-muted-foreground/30 bg-muted text-muted-foreground"
        )}
      >
        {service.configured ? <CheckCircle2 aria-hidden /> : <XCircle aria-hidden />}
        {service.configured ? "Konfiguriert" : "Nicht konfiguriert"}
      </Badge>
      <div className="text-xs">
        <p
          className={cn(
            "font-medium",
            testSuccessful
              ? "text-status-fulfilled"
              : testFailed
                ? "text-destructive"
                : "text-muted-foreground"
          )}
        >
          {SERVICE_TEST_LABEL[service.lastTestStatus]}
        </p>
        {service.lastTestAt && (
          <p className="mt-0.5 text-muted-foreground">{formatDateTime(service.lastTestAt)}</p>
        )}
        {service.availabilityNote && (
          <p className="mt-0.5 text-muted-foreground">{service.availabilityNote}</p>
        )}
      </div>
      <div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled
          aria-describedby={helpId}
        >
          Verbindung testen
        </Button>
        <p id={helpId} className="mt-1.5 max-w-52 text-xs text-muted-foreground">
          In der Beispielansicht nicht verfügbar.
        </p>
      </div>
    </li>
  )
}

function ServicesSection({ services }: { services: readonly KostenServiceViewModel[] }) {
  return (
    <section aria-labelledby="services-heading">
      <div>
        <h2 id="services-heading" className="text-lg font-semibold text-foreground">
          Dienste &amp; Verbindung
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Konfiguration und letzter bekannter Teststatus administrativer Dienste.
        </p>
      </div>
      <div className="mt-4 overflow-hidden rounded-xl border border-border bg-card">
        <ul className="divide-y divide-border">
          {services.map((service) => <ServiceRow key={service.id} service={service} />)}
        </ul>
        <div className="border-t border-border bg-muted/20 px-5 py-3">
          <p className="text-xs leading-relaxed text-muted-foreground">
            Schlüssel und Zugangsdaten sind nicht sichtbar. Ein Verbindungstest prüft
            Erreichbarkeit, nicht die fachliche Ergebnisqualität.
          </p>
        </div>
      </div>
    </section>
  )
}

export function KostenScreen({
  role,
  runs = RUNS,
  services = SERVICES,
  usage = USAGE_LIMITS,
}: KostenScreenProps) {
  const overview = React.useMemo(
    () => deriveKostenOverview(runs, usage.projectLimitChf),
    [runs, usage.projectLimitChf]
  )
  const expensiveRun = overview.mostExpensiveRun

  return (
    <div className="mx-auto flex w-full max-w-[1440px] flex-col gap-9 px-4 py-7 pb-12 sm:px-6 lg:px-8">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight text-foreground sm:text-[28px]">
          Kosten &amp; Laufzeit
        </h1>
        <p className="mt-1.5 max-w-3xl text-sm text-muted-foreground sm:text-base">
          Budgetverbrauch, Durchlauf-Historie sowie Kosten- und Latenzübersicht dieses Projekts.
        </p>
        <div role="note" className="mt-3 inline-flex max-w-3xl items-start gap-2 rounded-md border border-border bg-muted/25 px-3 py-2">
          <Info aria-hidden className="mt-0.5 size-3.5 shrink-0 text-muted-foreground" />
          <p className="text-xs leading-relaxed text-muted-foreground">
            Beispieldaten – Struktur und Darstellung entsprechen der geplanten Produktansicht.
          </p>
        </div>
      </header>

      <section aria-labelledby="overview-heading">
        <h2 id="overview-heading" className="sr-only">Projektüberblick</h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <MetricCard
            label="Projektverbrauch"
            value={`${formatCost(overview.totalCost)} von CHF ${usage.projectLimitChf.toFixed(2)}`}
            detail={`${COST_STATUS_LABELS[overview.totalCost.status]} · ${runs.length} Durchläufe`}
            icon={WalletCards}
          />
          <MetricCard
            label="Ø Kosten pro Lauf"
            value={formatCost(overview.averageCost)}
            detail={`${overview.knownCostRuns} von ${runs.length} Läufen mit Kostenwert`}
            icon={CircleDollarSign}
          />
          <MetricCard
            label="Ø Laufzeit"
            value={formatDuration(overview.averageDurationMs)}
            detail={`${overview.knownDurationRuns} von ${runs.length} Läufen mit End-to-End-Dauer`}
            icon={Timer}
          />
          <MetricCard
            label={overview.hasIncompleteCosts ? "Höchster bekannter Betrag" : "Teuerster Lauf"}
            value={expensiveRun ? formatCost(expensiveRun.cost) : "Nicht verfügbar"}
            detail={
              expensiveRun
                ? `${RUN_TYPE_LABELS[expensiveRun.type]} · ${formatDateTime(expensiveRun.startedAt)}`
                : "Kein vergleichbarer Kostenwert vorhanden"
            }
            icon={CircleDollarSign}
          />
        </div>
      </section>

      <UsageSection role={role} runs={runs} usage={usage} />
      <RunsTable runs={runs} />
      <ModelUsageTable runs={runs} />
      {role === "lead_admin" && <ServicesSection services={services} />}
    </div>
  )
}
