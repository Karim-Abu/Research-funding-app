"use client"

import * as React from "react"
import {
  getLiveSystemStatus,
  runLiveSystemPreflight,
  type LiveSystemStatusDto,
} from "@/lib/live-system-status"
import { AI_REASON_INFO } from "@/lib/redraft"

const OVERALL_LABEL = {
  available: "KI verfügbar",
  degraded: "Teilweise verfügbar",
  unavailable: "KI nicht verfügbar",
} as const

const PREFLIGHT_LABEL = {
  pass: "Bestanden",
  fail: "Fehlgeschlagen",
  not_run: "Nicht durchgeführt",
} as const

const GENERATION_LABEL = {
  real_eval: "Live-KI verfügbar",
  fake_demo: "Demo",
  unavailable: "Nicht verfügbar",
  live_unavailable: "Nicht verfügbar",
} as const

const FIRECRAWL_MODE_LABEL = {
  live: "Live-Firecrawl",
  fake: "Demo",
  disabled: "Nicht verfügbar",
  not_configured: "Nicht verfügbar",
} as const

// Zeitpunkt des letzten Preflights (de-CH); "—" solange keiner lief.
function formatTimestamp(value?: string | null): string {
  if (!value) return "—"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return "—"
  return date.toLocaleString("de-CH", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  })
}

export function LiveSystemStatus() {
  const [status, setStatus] = React.useState<LiveSystemStatusDto | null>(null)
  const [error, setError] = React.useState<string | null>(null)
  const [busy, setBusy] = React.useState(false)

  const load = React.useCallback(async () => {
    try {
      setError(null)
      setStatus(await getLiveSystemStatus())
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Status nicht verfügbar.")
    }
  }, [])

  React.useEffect(() => void load(), [load])

  async function preflight() {
    setBusy(true)
    setError(null)
    try {
      setStatus(await runLiveSystemPreflight())
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Preflight fehlgeschlagen.")
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="rounded-lg border border-border bg-card p-4" aria-labelledby="live-system-title">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 id="live-system-title" className="text-sm font-semibold">Live-Systemstatus</h2>
          <p className="text-xs text-muted-foreground">
            Nur sichere Metadaten. Der Preflight sendet ausschliesslich synthetische Testdaten.
          </p>
        </div>
        <button
          type="button"
          onClick={preflight}
          disabled={busy}
          className="rounded-md border border-border px-3 py-1.5 text-xs font-medium disabled:opacity-50"
        >
          {busy ? "Preflight läuft …" : "Synthetischen Preflight starten"}
        </button>
      </div>
      {error && <p className="mt-3 text-xs text-destructive">{error}</p>}
      {status && (
        <div className="mt-4 flex flex-col gap-3">
          <p className="text-sm font-medium">
            {GENERATION_LABEL[status.generation_mode]}
          </p>
          {status.generation_unavailable_reason && (
            <p className="text-xs text-muted-foreground">
              {AI_REASON_INFO[status.generation_unavailable_reason]?.text ??
                `Nächste Aktion: ${status.generation_unavailable_reason}`}
            </p>
          )}
          <p className="text-xs text-muted-foreground">
            Routenzustand: {OVERALL_LABEL[status.overall_status]}
          </p>
          <p className="text-xs text-muted-foreground">Registry: {status.registry_version}</p>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] text-left text-xs">
              <thead className="border-b border-border text-muted-foreground">
                <tr>
                  <th className="py-2 pr-3">Rolle / Route</th>
                  <th className="py-2 pr-3">Provider</th>
                  <th className="py-2 pr-3">Angefragt</th>
                  <th className="py-2 pr-3">Tatsächlich</th>
                  <th className="py-2 pr-3">Preflight</th>
                  <th className="py-2 pr-3">Zuletzt geprüft</th>
                  <th className="py-2 pr-3">Kostenstatus</th>
                  <th className="py-2">Nächste Aktion</th>
                </tr>
              </thead>
              <tbody>
                {status.routes.map((route) => (
                  <tr key={`${route.role_id}:${route.route_key}`} className="border-b border-border/60 align-top">
                    <td className="py-2 pr-3">
                      <div className="font-medium text-foreground">{route.role_id}</div>
                      <div className="text-muted-foreground">{route.route_alias}</div>
                    </td>
                    <td className="py-2 pr-3">{route.provider}</td>
                    <td className="py-2 pr-3">{route.requested_model_id ?? "nicht aufgelöst"}</td>
                    <td className="py-2 pr-3">{route.actual_model_id ?? "—"}</td>
                    <td className="py-2 pr-3">
                      {PREFLIGHT_LABEL[route.preflight_status]}
                      {route.error_class ? ` · ${route.error_class}` : ""}
                      {route.latency_ms != null ? ` · ${route.latency_ms} ms` : ""}
                    </td>
                    <td className="py-2 pr-3">
                      <div>{formatTimestamp(route.checked_at)}</div>
                      {route.expires_at && (
                        <div className="text-muted-foreground">
                          gültig bis {formatTimestamp(route.expires_at)}
                        </div>
                      )}
                    </td>
                    <td className="py-2 pr-3">{route.cost_status}</td>
                    <td className="py-2">
                      {route.readiness_reason
                        ? (AI_REASON_INFO[route.readiness_reason]?.ctaLabel ??
                          route.readiness_reason)
                        : "Keine"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="rounded-md border border-border/70 p-3">
            <p className="text-sm font-medium">
              {FIRECRAWL_MODE_LABEL[status.firecrawl.mode]}
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              Preflight: {PREFLIGHT_LABEL[status.firecrawl.preflight_status]}
              {status.firecrawl.error_class
                ? ` · ${status.firecrawl.error_class}`
                : ""}
              {status.firecrawl.latency_ms != null
                ? ` · ${status.firecrawl.latency_ms} ms`
                : ""}
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              Zuletzt geprüft: {formatTimestamp(status.firecrawl.checked_at)}
              {status.firecrawl.expires_at
                ? ` · gültig bis ${formatTimestamp(status.firecrawl.expires_at)}`
                : ""}
            </p>
          </div>
        </div>
      )}
    </section>
  )
}
