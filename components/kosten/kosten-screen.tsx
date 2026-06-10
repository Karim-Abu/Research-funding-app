"use client"

import * as React from "react"
import {
  ChevronRight,
  CheckCircle2,
  XCircle,
  Ban,
  OctagonX,
  Pencil,
  Check,
  X,
  Loader2,
  Wifi,
  WifiOff,
} from "lucide-react"
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Progress } from "@/components/ui/progress"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Separator } from "@/components/ui/separator"
import { cn } from "@/lib/utils"
import { RUNS, SERVICES, USAGE } from "@/lib/kosten-mock-data"
import type { Run, RunStatus, RunType, ServiceRow } from "@/lib/kosten-mock-data"
import type { Role } from "@/lib/types"

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface KostenScreenProps {
  role: Role
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const TYPE_LABEL: Record<RunType, string> = {
  analysis: "Analyse",
  section_regenerated: "Abschnitt neu erstellt",
  web_search: "Webrecherche",
}

const STATUS_CONFIG: Record<
  RunStatus,
  { label: string; variant: "default" | "secondary" | "destructive" | "outline"; icon: React.ElementType; className: string }
> = {
  completed: {
    label: "Abgeschlossen",
    variant: "outline",
    icon: CheckCircle2,
    className: "border-status-fulfilled/40 bg-status-fulfilled/10 text-status-fulfilled",
  },
  stopped_cost: {
    label: "Gestoppt: Kostenlimit",
    variant: "outline",
    icon: OctagonX,
    className: "border-status-partial/40 bg-status-partial/10 text-status-partial",
  },
  failed: {
    label: "Fehlgeschlagen",
    variant: "outline",
    icon: XCircle,
    className: "border-destructive/40 bg-destructive/10 text-destructive",
  },
  cancelled: {
    label: "Abgebrochen",
    variant: "outline",
    icon: Ban,
    className: "border-muted-foreground/40 bg-muted text-muted-foreground",
  },
}

function usageColor(percent: number): string {
  if (percent >= 100) return "bg-destructive"
  if (percent >= 80) return "bg-status-partial"
  return "bg-status-fulfilled"
}

// ---------------------------------------------------------------------------
// Usage bar section
// ---------------------------------------------------------------------------

function UsageSection({ role }: { role: Role }) {
  const { usedChf, limitChf, perRunLimitChf } = USAGE
  const percent = Math.round((usedChf / limitChf) * 100)
  const isStopped = percent >= 100
  const isWarning = percent >= 80 && percent < 100

  const [editing, setEditing] = React.useState(false)
  const [limitValue, setLimitValue] = React.useState(String(perRunLimitChf))
  const [error, setError] = React.useState<string | null>(null)

  function handleSave() {
    const val = Number(limitValue)
    if (isNaN(val) || val < 1 || val > 50) {
      setError("Maximal CHF 50 pro Durchlauf — vom Admin festgelegt.")
      return
    }
    setError(null)
    setEditing(false)
  }

  function handleCancel() {
    setLimitValue(String(perRunLimitChf))
    setError(null)
    setEditing(false)
  }

  return (
    <section aria-labelledby="usage-heading">
      <h2
        id="usage-heading"
        className="mb-4 text-base font-semibold text-foreground"
      >
        Verbrauch &amp; Limits
      </h2>

      <div className="rounded-lg border border-border bg-card p-5">
        {/* Stopped banner */}
        {isStopped && (
          <div className="mb-4 flex items-start gap-2 rounded-md border border-destructive/40 bg-destructive/8 px-3 py-2.5">
            <OctagonX className="mt-0.5 size-4 shrink-0 text-destructive" />
            <p className="text-sm text-destructive">
              Durchläufe gestoppt — Projektlimit erreicht.
            </p>
          </div>
        )}

        {/* Usage bar */}
        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-foreground">
              ~CHF {usedChf} von CHF {limitChf}{" "}
              <span className="font-normal text-muted-foreground">(Dummy)</span>
            </span>
            <span
              className={cn(
                "text-sm font-semibold tabular-nums",
                isStopped
                  ? "text-destructive"
                  : isWarning
                  ? "text-status-partial"
                  : "text-status-fulfilled"
              )}
            >
              {percent} %
            </span>
          </div>
          <div className="h-2.5 w-full overflow-hidden rounded-full bg-muted">
            <div
              className={cn(
                "h-full rounded-full transition-all",
                usageColor(percent)
              )}
              style={{ width: `${Math.min(percent, 100)}%` }}
              role="presentation"
            />
          </div>
          {isWarning && !isStopped && (
            <p className="text-xs text-status-partial">
              Über 80 % des Projektlimits verbraucht.
            </p>
          )}
        </div>

        <Separator className="my-4" />

        {/* Per-run limit */}
        <div className="flex items-center justify-between gap-4">
          <div className="flex flex-col gap-0.5">
            <span className="text-sm text-foreground">Limit pro Durchlauf</span>
            {!editing && (
              <span className="text-sm font-medium text-foreground">
                CHF {perRunLimitChf}{" "}
                <span className="font-normal text-muted-foreground">(Dummy)</span>
              </span>
            )}
          </div>

          {role === "lead_admin" && !editing && (
            <button
              type="button"
              aria-label="Limit pro Durchlauf bearbeiten"
              onClick={() => setEditing(true)}
              className={cn(
                "flex size-8 items-center justify-center rounded text-muted-foreground",
                "transition-colors hover:bg-accent hover:text-foreground",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              )}
            >
              <Pencil className="size-4" />
            </button>
          )}
        </div>

        {/* Inline edit form — lead_admin only */}
        {role === "lead_admin" && editing && (
          <div className="mt-3 flex flex-col gap-2">
            <Label htmlFor="per-run-limit" className="text-sm">
              Limit pro Durchlauf (CHF)
            </Label>
            <div className="flex items-center gap-2">
              <Input
                id="per-run-limit"
                type="number"
                min={1}
                max={50}
                value={limitValue}
                onChange={(e) => {
                  setLimitValue(e.target.value)
                  setError(null)
                }}
                className="w-28"
                autoFocus
              />
              <button
                type="button"
                aria-label="Speichern"
                onClick={handleSave}
                className={cn(
                  "flex size-8 items-center justify-center rounded bg-foreground text-background",
                  "hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                )}
              >
                <Check className="size-4" />
              </button>
              <button
                type="button"
                aria-label="Abbrechen"
                onClick={handleCancel}
                className={cn(
                  "flex size-8 items-center justify-center rounded text-muted-foreground",
                  "hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                )}
              >
                <X className="size-4" />
              </button>
            </div>
            {error && (
              <p className="text-xs text-destructive">{error}</p>
            )}
          </div>
        )}

        <Separator className="my-4" />

        <p className="text-xs text-muted-foreground">
          Beim Erreichen eines Limits stoppt der Durchlauf automatisch. Dieser
          Schutz lässt sich nicht abschalten.
        </p>
      </div>
    </section>
  )
}

// ---------------------------------------------------------------------------
// Run detail drawer
// ---------------------------------------------------------------------------

function RunDrawer({
  run,
  open,
  onOpenChange,
}: {
  run: Run | null
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  if (!run) return null

  const statusCfg = STATUS_CONFIG[run.status]
  const StatusIcon = statusCfg.icon

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        className="flex w-[480px] flex-col gap-0 overflow-y-auto p-0 sm:max-w-[480px]"
      >
        <SheetHeader className="border-b border-border px-6 py-5">
          <SheetTitle className="text-base">
            {TYPE_LABEL[run.type]}
          </SheetTitle>
          <SheetDescription className="text-xs text-muted-foreground">
            {run.date} · {run.user}
          </SheetDescription>
        </SheetHeader>

        <div className="flex flex-col gap-5 px-6 py-5">
          {/* Status */}
          <div className="flex flex-col gap-1.5">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Status
            </p>
            <span
              className={cn(
                "inline-flex w-fit items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium",
                statusCfg.className
              )}
            >
              <StatusIcon className="size-3.5" />
              {statusCfg.label}
            </span>
            {run.stopReason && (
              <p className="text-sm text-foreground">{run.stopReason}</p>
            )}
          </div>

          <Separator />

          {/* Einstellungen */}
          <div className="flex flex-col gap-3">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Einstellungen
            </p>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
              <dt className="text-muted-foreground">KI-Unterstützung</dt>
              <dd className="font-medium text-foreground">
                {run.kiEnabled ? "An" : "Aus"}
              </dd>
              <dt className="text-muted-foreground">Webrecherche</dt>
              <dd className="font-medium text-foreground">
                {run.webEnabled ? "An" : "Aus"}
              </dd>
              <dt className="text-muted-foreground">KI-Modell</dt>
              <dd className="font-medium text-foreground">{run.model}</dd>
              <dt className="text-muted-foreground">Verwendeter Umfang</dt>
              <dd className="font-medium text-foreground">{run.tokensUsed}</dd>
              <dt className="text-muted-foreground">Ungefähre Kosten</dt>
              <dd className="font-medium text-foreground">
                {run.approximateCost}
              </dd>
            </dl>
          </div>

          <Separator />

          {/* Audit */}
          <div className="flex flex-col gap-1.5">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Audit
            </p>
            <p className="text-sm text-foreground">
              Im Audit gespeichert (Referenz: {run.auditRef})
            </p>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  )
}

// ---------------------------------------------------------------------------
// Runs table section
// ---------------------------------------------------------------------------

function RunsSection() {
  const [openRun, setOpenRun] = React.useState<Run | null>(null)
  const [drawerOpen, setDrawerOpen] = React.useState(false)

  function handleRowClick(run: Run) {
    setOpenRun(run)
    setDrawerOpen(true)
  }

  return (
    <section aria-labelledby="runs-heading">
      <h2
        id="runs-heading"
        className="mb-4 text-base font-semibold text-foreground"
      >
        Durchläufe
      </h2>

      {RUNS.length === 0 ? (
        <div className="flex min-h-[120px] items-center justify-center rounded-lg border border-border bg-card px-6 py-8 text-center">
          <p className="text-sm text-muted-foreground">
            Noch keine Durchläufe. Kosten entstehen erst, wenn Sie eine Analyse
            starten.
          </p>
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg border border-border bg-card">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border">
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Datum
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Art
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Nutzer:in
                </th>
                <th className="px-4 py-3 text-center text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  KI
                </th>
                <th className="px-4 py-3 text-center text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Web
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  ~Kosten
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Status
                </th>
                <th className="w-10 px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {RUNS.map((run) => {
                const statusCfg = STATUS_CONFIG[run.status]
                const StatusIcon = statusCfg.icon
                return (
                  <tr
                    key={run.id}
                    onClick={() => handleRowClick(run)}
                    className={cn(
                      "cursor-pointer transition-colors hover:bg-accent/50",
                      "focus-within:bg-accent/50"
                    )}
                    tabIndex={0}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault()
                        handleRowClick(run)
                      }
                    }}
                    aria-label={`Durchlauf ${run.date} details öffnen`}
                  >
                    <td className="min-h-[44px] px-4 py-3 text-sm text-foreground">
                      {run.date}
                    </td>
                    <td className="px-4 py-3 text-sm text-foreground">
                      {TYPE_LABEL[run.type]}
                    </td>
                    <td className="px-4 py-3 text-sm text-muted-foreground">
                      {run.user}
                    </td>
                    <td className="px-4 py-3 text-center">
                      {run.kiEnabled ? (
                        <Wifi className="mx-auto size-4 text-status-fulfilled" aria-label="an" />
                      ) : (
                        <WifiOff className="mx-auto size-4 text-muted-foreground/50" aria-label="aus" />
                      )}
                    </td>
                    <td className="px-4 py-3 text-center">
                      {run.webEnabled ? (
                        <Wifi className="mx-auto size-4 text-status-fulfilled" aria-label="an" />
                      ) : (
                        <WifiOff className="mx-auto size-4 text-muted-foreground/50" aria-label="aus" />
                      )}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums text-sm text-foreground">
                      {run.approximateCost}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={cn(
                          "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium",
                          statusCfg.className
                        )}
                      >
                        <StatusIcon className="size-3" />
                        {statusCfg.label}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <ChevronRight className="size-4 text-muted-foreground" />
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      <RunDrawer
        run={openRun}
        open={drawerOpen}
        onOpenChange={setDrawerOpen}
      />
    </section>
  )
}

// ---------------------------------------------------------------------------
// Dienste section (lead_admin only — not rendered for members)
// ---------------------------------------------------------------------------

type TestState = "idle" | "testing" | "ok" | "error"

function ServiceRow({ svc }: { svc: ServiceRow }) {
  const [testState, setTestState] = React.useState<TestState>("idle")

  function handleTest() {
    setTestState("testing")
    const outcome: TestState = svc.configured ? "ok" : "error"
    setTimeout(() => setTestState(outcome), 1400)
  }

  return (
    <div className="flex min-h-[56px] items-center gap-4 px-5 py-3">
      <div className="flex-1">
        <span className="text-sm font-medium text-foreground">{svc.name}</span>
      </div>

      {/* Status badge */}
      <span
        className={cn(
          "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium",
          svc.configured
            ? "border-status-fulfilled/40 bg-status-fulfilled/10 text-status-fulfilled"
            : "border-muted-foreground/30 bg-muted text-muted-foreground"
        )}
      >
        {svc.configured ? (
          <CheckCircle2 className="size-3" />
        ) : (
          <XCircle className="size-3" />
        )}
        {svc.configured ? "Konfiguriert" : "Nicht konfiguriert"}
      </span>

      {/* Test button */}
      <Button
        variant="outline"
        size="sm"
        disabled={testState === "testing"}
        onClick={handleTest}
        className="w-40 shrink-0"
      >
        {testState === "testing" ? (
          <>
            <Loader2 className="mr-1.5 size-3.5 animate-spin" />
            Wird getestet…
          </>
        ) : (
          "Verbindung testen"
        )}
      </Button>

      {/* Result line — shown in place after testing */}
      <div className="w-52 shrink-0 text-xs">
        {testState === "ok" && (
          <span className="text-status-fulfilled">
            Verbindung erfolgreich · vor 1 Min.
          </span>
        )}
        {testState === "error" && (
          <span className="text-destructive">
            Dienst aktuell nicht verfügbar.
          </span>
        )}
      </div>
    </div>
  )
}

function DiensteSection() {
  return (
    <section aria-labelledby="dienste-heading">
      <h2
        id="dienste-heading"
        className="mb-4 text-base font-semibold text-foreground"
      >
        Dienste
      </h2>
      <div className="overflow-hidden rounded-lg border border-border bg-card">
        <div className="divide-y divide-border">
          {SERVICES.map((svc) => (
            <ServiceRow key={svc.id} svc={svc} />
          ))}
        </div>
        <div className="border-t border-border px-5 py-3">
          <p className="text-xs text-muted-foreground">
            Verbindungen werden serverseitig konfiguriert. Schlüssel und
            Zugangsdaten sind hier nicht sichtbar.
          </p>
        </div>
      </div>
    </section>
  )
}

// ---------------------------------------------------------------------------
// Main screen
// ---------------------------------------------------------------------------

export function KostenScreen({ role }: KostenScreenProps) {
  return (
    <div className="flex flex-col gap-8 px-6 py-8 pb-12">
      {/* Page header */}
      <div>
        <h1 className="text-xl font-semibold text-foreground">
          Kosten &amp; Laufzeit
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Verbrauch, Limits und Durchlauf-Historie dieses Projekts.
        </p>
      </div>

      <UsageSection role={role} />
      <RunsSection />
      {role === "lead_admin" && <DiensteSection />}
    </div>
  )
}
