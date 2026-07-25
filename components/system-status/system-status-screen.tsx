"use client"

import * as React from "react"
import { CheckCircle2, CircleAlert, RefreshCw, WifiOff } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  getSystemStatus,
  runConnectionCheck,
  type SystemServiceState,
  type SystemStatusDto,
} from "@/lib/system-status"
import { cn } from "@/lib/utils"

const STATE_COPY: Record<SystemServiceState, { label: string; icon: typeof CheckCircle2; tone: string }> = {
  available: { label: "Verfügbar", icon: CheckCircle2, tone: "border-status-fulfilled/35 bg-status-fulfilled/8 text-status-fulfilled" },
  attention: { label: "Prüfung empfohlen", icon: CircleAlert, tone: "border-status-partial/35 bg-status-partial/8 text-status-partial" },
  unavailable: { label: "Nicht verfügbar", icon: WifiOff, tone: "border-destructive/35 bg-destructive/8 text-destructive" },
}

function formatCheckedAt(value?: string | null): string {
  if (!value) return "Noch nicht geprüft"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return "Zeitpunkt nicht verfügbar"
  return `Zuletzt geprüft: ${date.toLocaleString("de-CH", { dateStyle: "medium", timeStyle: "short" })}`
}

export function SystemStatusScreen() {
  const [data, setData] = React.useState<SystemStatusDto | null>(null)
  const [error, setError] = React.useState<string | null>(null)
  const [checking, setChecking] = React.useState(false)

  const load = React.useCallback(async () => {
    try {
      setError(null)
      setData(await getSystemStatus())
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Systemstatus konnte nicht geladen werden.")
    }
  }, [])

  React.useEffect(() => void load(), [load])

  async function checkConnection() {
    setChecking(true)
    try {
      setError(null)
      setData(await runConnectionCheck())
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Verbindung konnte nicht geprüft werden.")
    } finally {
      setChecking(false)
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-7 px-4 py-7 pb-12 sm:px-6 lg:px-8">
      <header className="max-w-3xl">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground sm:text-[28px]">Systemstatus</h1>
        <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground sm:text-base">
          Hier sehen Sie, ob die unterstützenden Dienste bereit sind. Rollen und Modelle werden unter Rollen &amp; Verantwortung erklärt.
        </p>
      </header>

      {error && (
        <div role="alert" className="rounded-xl border border-destructive/35 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {!data && !error && <div className="h-40 animate-pulse rounded-xl border border-border bg-muted/40" />}

      {data && (
        <>
          <section className="grid gap-4 sm:grid-cols-2" aria-label="Verfügbarkeit der Dienste">
            {data.services.map((service) => {
              const state = STATE_COPY[service.state]
              const Icon = state.icon
              return (
                <article key={service.id} className="rounded-xl border border-border bg-card p-5 shadow-sm">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h2 className="text-base font-semibold text-foreground">{service.label}</h2>
                      <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">{service.message}</p>
                    </div>
                    <span className={cn("inline-flex shrink-0 items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium", state.tone)}>
                      <Icon aria-hidden className="size-3.5" />
                      {state.label}
                    </span>
                  </div>
                  <div className="mt-5 border-t border-border pt-3 text-xs text-muted-foreground">
                    <p>{formatCheckedAt(service.checked_at)}</p>
                    <p className="mt-1"><span className="font-medium text-foreground">Nächster Schritt:</span> {service.next_step}</p>
                  </div>
                </article>
              )
            })}
          </section>

          <section className="rounded-xl border border-border bg-muted/20 p-5" aria-labelledby="connection-check-heading">
            <h2 id="connection-check-heading" className="text-base font-semibold text-foreground">Verbindung prüfen</h2>
            <p className="mt-1.5 max-w-2xl text-sm leading-relaxed text-muted-foreground">
              Der Test verwendet ausschliesslich harmlose Testdaten und überträgt keine Projektinhalte.
            </p>
            {data.can_run_connection_check ? (
              <Button className="mt-4" variant="outline" onClick={checkConnection} disabled={checking}>
                <RefreshCw data-icon="inline-start" className={checking ? "animate-spin" : undefined} />
                {checking ? "Verbindung wird geprüft …" : "Verbindung mit Testdaten prüfen"}
              </Button>
            ) : (
              <p className="mt-4 text-sm text-muted-foreground">Ein Lead-Admin kann die Verbindung bei Bedarf prüfen.</p>
            )}
          </section>
        </>
      )}
    </div>
  )
}
