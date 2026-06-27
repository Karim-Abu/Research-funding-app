"use client"

import * as React from "react"
import { AlertTriangle, RefreshCw } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import {
  listRequirements,
  STATUS_LABELS,
  BASIS_LABELS,
  STALE_NOTICE,
  type RequirementAssessmentDto,
  type RequirementStatus,
} from "@/lib/requirements"

const STATUS_VARIANT: Record<
  RequirementStatus,
  "default" | "secondary" | "outline" | "destructive"
> = {
  fulfilled: "default",
  partial: "secondary",
  open: "outline",
  needs_input: "outline",
  blocked: "destructive",
}

export function LiveRequirements({ runId }: { runId: string }) {
  const [items, setItems] = React.useState<RequirementAssessmentDto[] | null>(
    null
  )
  const [error, setError] = React.useState<string | null>(null)

  const load = React.useCallback(() => {
    setError(null)
    setItems(null)
    listRequirements(runId)
      .then(setItems)
      .catch((e) => setError(e instanceof Error ? e.message : "Fehler."))
  }, [runId])

  React.useEffect(() => load(), [load])

  if (error) {
    return (
      <div className="mx-auto max-w-4xl px-6 py-10 text-center">
        <p className="text-sm text-muted-foreground">{error}</p>
        <Button variant="outline" className="mt-4" onClick={load}>
          <RefreshCw data-icon="inline-start" />
          Erneut versuchen
        </Button>
      </div>
    )
  }

  if (items === null) {
    return (
      <div className="mx-auto max-w-4xl space-y-3 px-6 py-10">
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-16 w-full" />
        ))}
      </div>
    )
  }

  const stale = items.some((a) => a.stale)

  return (
    <div className="mx-auto max-w-4xl px-6 py-10">
      <header className="mb-6">
        <h1 className="text-xl font-semibold">Fördervoraussetzungen</h1>
        <p className="text-sm text-muted-foreground">
          Deterministische Vorprüfung der formalen Fördervoraussetzungen und
          verfügbaren Angaben. Inhaltliche Bewertung und Belege folgen in
          späteren Schritten.
        </p>
      </header>

      {stale && (
        <div
          role="alert"
          className="mb-6 flex items-start gap-2 rounded-md border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900"
        >
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{STALE_NOTICE}</span>
        </div>
      )}

      <ul className="divide-y divide-border rounded-lg border border-border">
        {items.map((a) => (
          <li key={a.assessment_id} className="px-4 py-4">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-sm font-medium">
                  {a.title ?? a.requirement_id}
                </p>
                <p className="mt-1 text-sm text-muted-foreground">
                  {a.reasoning}
                </p>
              </div>
              <Badge variant={STATUS_VARIANT[a.status]}>
                {STATUS_LABELS[a.status]}
              </Badge>
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <Badge variant="outline">{BASIS_LABELS[a.basis]}</Badge>
              {a.open_issues.map((issue) => (
                <span
                  key={issue.issue_id}
                  className="text-xs text-muted-foreground"
                >
                  → {issue.recommended_next_action}
                </span>
              ))}
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}
