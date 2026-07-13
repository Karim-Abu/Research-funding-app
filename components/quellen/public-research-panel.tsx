"use client"

// "Öffentliche Recherche" — user-initiated public web research (M9I-A) with the M9J
// Search Query Firewall for confidential projects. For a public (D0) project the query
// runs directly. For an internal/confidential (D1/D2) project the query is first screened
// and sanitized; only a human-approved, sanitized query is ever searched. For D3 (NDA)
// and UNKNOWN the panel is fully blocked (R4.1) — the backend matrix enforces the same.
// No provider/Firecrawl/API terminology and no raw confidential query is surfaced.

import * as React from "react"
import { Globe, Loader2, ShieldAlert, Sparkles } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { pollOperation } from "@/lib/operations"
import {
  createResearchTask,
  importResearchResult,
  listResearchResults,
  ResearchError,
  type ResearchResultDto,
} from "@/lib/research"
import {
  approveSearchQuery,
  previewSearchQuery,
  FirewallError,
  type FirewallPreview,
} from "@/lib/firewall"
import {
  flatToPrivacyClass,
  isExternalBlocked,
  requiresSanitizedApproval,
} from "@/lib/data-class"
import type { DataClass } from "@/lib/types"

type PanelState =
  | "idle"
  | "previewing"
  | "preview"
  | "blocked"
  | "searching"
  | "results"
  | "error"

function hostOf(url: string): string {
  try {
    return new URL(url).hostname
  } catch {
    return url
  }
}

export function PublicResearchPanel({
  projectId,
  dataClass = "public",
  onImported,
}: {
  projectId: string
  dataClass?: DataClass
  onImported?: () => void
}) {
  const privacyClass = flatToPrivacyClass(dataClass)
  const researchBlocked = isExternalBlocked(privacyClass)
  const needsFirewall = requiresSanitizedApproval(privacyClass)

  const [query, setQuery] = React.useState("")
  const [state, setState] = React.useState<PanelState>("idle")
  const [error, setError] = React.useState<string | null>(null)
  const [preview, setPreview] = React.useState<FirewallPreview | null>(null)
  const [results, setResults] = React.useState<ResearchResultDto[]>([])
  const [importing, setImporting] = React.useState<Record<string, boolean>>({})
  const [imported, setImported] = React.useState<Record<string, boolean>>({})
  const pollRef = React.useRef<{ stop: () => void } | null>(null)

  React.useEffect(() => () => pollRef.current?.stop(), [])

  const busy = state === "searching" || state === "previewing"
  const submitLabel = needsFirewall ? "Vor Webrecherche prüfen" : "Suchen"

  // Run the actual research task (public query, or an approved sanitized query).
  const runTask = React.useCallback(
    async (queryPreview: string, approvalId?: string) => {
      setState("searching")
      setError(null)
      setResults([])
      try {
        const accepted = await createResearchTask(projectId, {
          purpose: "partner_role_suggestion",
          subject_type: "topic",
          query_preview: queryPreview,
          max_results: 5,
          ...(approvalId ? { approval_id: approvalId } : {}),
        })
        pollRef.current = pollOperation(accepted.operation_id, {
          onTerminal: async (op) => {
            if (op.status !== "succeeded") {
              setState("error")
              setError(
                "Die Recherche konnte nicht abgeschlossen werden. Bitte versuchen Sie es später erneut."
              )
              return
            }
            try {
              const rows = await listResearchResults(projectId)
              setResults(rows.filter((r) => r.task_id === accepted.resource_id))
              setState("results")
            } catch {
              setState("error")
              setError("Die Ergebnisse konnten nicht geladen werden.")
            }
          },
        })
      } catch (err) {
        setState("error")
        setError(
          err instanceof ResearchError ? err.message : "Es ist ein Fehler aufgetreten."
        )
      }
    },
    [projectId]
  )

  const onSubmit = React.useCallback(
    async (event: React.FormEvent) => {
      event.preventDefault()
      const trimmed = query.trim()
      if (!trimmed || busy) return
      setError(null)
      setPreview(null)
      if (!needsFirewall) {
        await runTask(trimmed)
        return
      }
      // Confidential: screen + sanitize before anything is searched.
      setState("previewing")
      try {
        const result = await previewSearchQuery(projectId, trimmed)
        setPreview(result)
        setState(result.decision === "block" ? "blocked" : "preview")
      } catch (err) {
        setState("error")
        setError(
          err instanceof FirewallError ? err.message : "Es ist ein Fehler aufgetreten."
        )
      }
    },
    [query, busy, needsFirewall, projectId, runTask]
  )

  const approveAndSearch = React.useCallback(async () => {
    if (!preview?.approval_id) return
    setState("searching")
    try {
      await approveSearchQuery(preview.approval_id)
      await runTask(query.trim(), preview.approval_id)
    } catch (err) {
      setState("error")
      setError(
        err instanceof FirewallError ? err.message : "Es ist ein Fehler aufgetreten."
      )
    }
  }, [preview, query, runTask])

  const importOne = React.useCallback(
    async (resultId: string) => {
      setImporting((m) => ({ ...m, [resultId]: true }))
      try {
        await importResearchResult(resultId)
        setImported((m) => ({ ...m, [resultId]: true }))
        onImported?.()
      } catch (err) {
        setError(
          err instanceof ResearchError
            ? err.message
            : "Die Quelle konnte nicht importiert werden."
        )
      } finally {
        setImporting((m) => ({ ...m, [resultId]: false }))
      }
    },
    [onImported]
  )

  // R4.1: D3 (NDA) / unklassifiziert — keine Webrecherche, auch nicht sanitisiert.
  if (researchBlocked) {
    return (
      <section
        data-testid="public-research-panel"
        className="rounded-lg border border-border bg-card p-5"
      >
        <div className="mb-1 flex items-center gap-2">
          <ShieldAlert className="size-4 text-status-partial" />
          <h3 className="text-sm font-semibold text-foreground">
            Öffentliche Recherche
          </h3>
        </div>
        <p data-testid="research-blocked" className="text-xs text-muted-foreground">
          Für NDA-geschützte, gesperrte oder noch nicht eingestufte Inhalte ist
          keine Webrecherche möglich. Es werden keine externen Dienste aufgerufen.
        </p>
      </section>
    )
  }

  return (
    <section
      data-testid="public-research-panel"
      className="rounded-lg border border-border bg-card p-5"
    >
      <div className="mb-1 flex items-center gap-2">
        <Globe className="size-4 text-muted-foreground" />
        <h3 className="text-sm font-semibold text-foreground">Öffentliche Recherche</h3>
      </div>
      <p className="mb-3 text-xs text-muted-foreground">
        {needsFirewall
          ? "Diese Anfrage enthält möglicherweise vertrauliche Angaben. Sie wird vor der Websuche geprüft und bereinigt."
          : "Nur öffentliche Suchbegriffe verwenden. Keine vertraulichen oder personenbezogenen Informationen eingeben."}
      </p>

      <form onSubmit={onSubmit} className="flex flex-col gap-2 sm:flex-row">
        <div className="flex-1">
          <Label htmlFor="research-query" className="sr-only">
            Öffentlicher Suchbegriff
          </Label>
          <Input
            id="research-query"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value)
              if (state === "preview" || state === "blocked") setState("idle")
            }}
            placeholder="z. B. öffentliche Forschungskompetenz Photonik"
            disabled={busy}
          />
        </div>
        <Button type="submit" disabled={busy || !query.trim()}>
          {busy ? (
            <>
              <Loader2 className="size-4 animate-spin" />{" "}
              {state === "previewing" ? "Prüfung läuft …" : "Suche läuft …"}
            </>
          ) : (
            submitLabel
          )}
        </Button>
      </form>

      {/* Firewall preview — sanitized query + approval (D1/D2, require_human_approval) */}
      {state === "preview" && preview && (
        <div
          data-testid="firewall-preview"
          className="mt-4 rounded-md border border-status-partial/40 bg-status-partial/8 p-3"
        >
          <p className="flex items-center gap-1.5 text-sm font-medium text-foreground">
            <ShieldAlert className="size-4 text-status-partial" />
            Bereinigte Suchanfrage
          </p>
          <p
            data-testid="sanitized-query"
            className="mt-2 rounded bg-background px-2 py-1.5 text-sm text-foreground"
          >
            {preview.sanitized_query || "—"}
          </p>
          {preview.redaction_summary.length > 0 && (
            <div className="mt-2">
              <p className="text-xs text-muted-foreground">
                Entfernte oder verallgemeinerte Angaben:
              </p>
              <ul className="mt-1 flex flex-wrap gap-1.5">
                {preview.redaction_summary.map((r) => (
                  <li key={r.category}>
                    <Badge variant="secondary">
                      {r.label}
                      {r.count > 1 ? ` ×${r.count}` : ""}
                    </Badge>
                  </li>
                ))}
              </ul>
            </div>
          )}
          <p className="mt-2 text-xs text-muted-foreground">
            Die Websuche erhält nur die bereinigte Anfrage.
          </p>
          <div className="mt-3 flex gap-2">
            <Button type="button" size="sm" onClick={approveAndSearch}>
              Bereinigte Anfrage freigeben und suchen
            </Button>
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => setState("idle")}
            >
              Anfrage anpassen
            </Button>
          </div>
        </div>
      )}

      {/* Firewall block — cannot be safely sanitized */}
      {state === "blocked" && preview && (
        <div
          data-testid="firewall-blocked"
          role="alert"
          className="mt-4 rounded-md border border-destructive/30 bg-destructive/5 p-3"
        >
          <p className="flex items-center gap-1.5 text-sm font-medium text-foreground">
            <ShieldAlert className="size-4 text-destructive" />
            Diese Suchanfrage kann nicht sicher bereinigt werden.
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            Bitte formulieren Sie die Anfrage allgemeiner (ohne Partner-, Projekt- oder
            Budgetangaben).
          </p>
        </div>
      )}

      {error && (
        <p role="alert" className="mt-3 text-sm text-status-incomplete">
          {error}
        </p>
      )}

      {state === "results" && results.length === 0 && (
        <p className="mt-4 text-sm text-muted-foreground">
          Keine öffentlichen Ergebnisse gefunden.
        </p>
      )}

      {results.length > 0 && (
        <ul className="mt-4 flex flex-col gap-3" data-testid="research-results">
          {results.map((r) => (
            <li
              key={r.result_id}
              className="rounded-md border border-border bg-background p-3"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-foreground">
                    {r.title}
                  </p>
                  <p className="truncate text-xs text-muted-foreground">
                    {hostOf(r.source_url)}
                  </p>
                  {r.snippet && (
                    <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">
                      {r.snippet}
                    </p>
                  )}
                </div>
                {imported[r.result_id] || r.status === "imported" ? (
                  <Badge variant="secondary" className="shrink-0">
                    Als Quelle gespeichert
                  </Badge>
                ) : (
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    className="shrink-0"
                    disabled={importing[r.result_id]}
                    onClick={() => importOne(r.result_id)}
                  >
                    {importing[r.result_id] ? (
                      <Loader2 className="size-3.5 animate-spin" />
                    ) : (
                      "Quelle importieren"
                    )}
                  </Button>
                )}
              </div>
              {r.partner_role_suggestions.length > 0 && (
                <p className="mt-2 flex items-center gap-1 text-xs text-muted-foreground">
                  <Sparkles className="size-3" />
                  KI-gestützte Vorschläge — fachlich zu prüfen.
                </p>
              )}
            </li>
          ))}
        </ul>
      )}

      <p className="mt-4 text-xs text-muted-foreground">
        Webquellen müssen fachlich geprüft werden.
      </p>
    </section>
  )
}
