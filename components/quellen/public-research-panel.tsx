"use client"

// "Öffentliche Recherche" — user-initiated public web research (M9I-A).
// Enter a public query, run a controlled search, review candidates, import one as a
// normal source. No provider/Firecrawl/API terminology is ever shown. Imported page
// text becomes source material; it is not evidence until the deterministic pipeline runs.

import * as React from "react"
import { Globe, Loader2, Sparkles } from "lucide-react"

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

type PanelState = "idle" | "searching" | "results" | "error"

function hostOf(url: string): string {
  try {
    return new URL(url).hostname
  } catch {
    return url
  }
}

export function PublicResearchPanel({
  projectId,
  onImported,
}: {
  projectId: string
  onImported?: () => void
}) {
  const [query, setQuery] = React.useState("")
  const [state, setState] = React.useState<PanelState>("idle")
  const [error, setError] = React.useState<string | null>(null)
  const [results, setResults] = React.useState<ResearchResultDto[]>([])
  const [importing, setImporting] = React.useState<Record<string, boolean>>({})
  const [imported, setImported] = React.useState<Record<string, boolean>>({})
  const pollRef = React.useRef<{ stop: () => void } | null>(null)

  React.useEffect(() => () => pollRef.current?.stop(), [])

  const runSearch = React.useCallback(
    async (event: React.FormEvent) => {
      event.preventDefault()
      const trimmed = query.trim()
      if (!trimmed || state === "searching") return
      setState("searching")
      setError(null)
      setResults([])
      try {
        const accepted = await createResearchTask(projectId, {
          purpose: "partner_role_suggestion",
          subject_type: "topic",
          query_preview: trimmed,
          max_results: 5,
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
          err instanceof ResearchError
            ? err.message
            : "Es ist ein Fehler aufgetreten."
        )
      }
    },
    [projectId, query, state]
  )

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

  return (
    <section
      data-testid="public-research-panel"
      className="rounded-lg border border-border bg-card p-5"
    >
      <div className="mb-1 flex items-center gap-2">
        <Globe className="size-4 text-muted-foreground" />
        <h3 className="text-sm font-semibold text-foreground">
          Öffentliche Recherche
        </h3>
      </div>
      <p className="mb-3 text-xs text-muted-foreground">
        Nur öffentliche Suchbegriffe verwenden. Keine vertraulichen oder
        personenbezogenen Informationen eingeben.
      </p>

      <form onSubmit={runSearch} className="flex flex-col gap-2 sm:flex-row">
        <div className="flex-1">
          <Label htmlFor="research-query" className="sr-only">
            Öffentlicher Suchbegriff
          </Label>
          <Input
            id="research-query"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="z. B. öffentliche Forschungskompetenz Photonik"
            disabled={state === "searching"}
          />
        </div>
        <Button type="submit" disabled={state === "searching" || !query.trim()}>
          {state === "searching" ? (
            <>
              <Loader2 className="size-4 animate-spin" /> Suche läuft …
            </>
          ) : (
            "Suchen"
          )}
        </Button>
      </form>

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
