"use client"

// R8 — Freigabe der geplanten Suchanfragen (HITL): der Nutzer sieht jede ausgehende
// Query und kann sie Freigeben, Ablehnen oder Bearbeiten. Bearbeiten prüft den neuen
// Text erneut durch die Search Query Firewall und erzeugt eine NEUE Freigabe; die
// alte wird abgelehnt. Ohne Freigabe wird keine Query ausgeführt. Wiederverwendet vom
// Analyse-Dialog und vom Market-Panel im Editor.

import * as React from "react"
import { Check, Loader2, Pencil, X } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { approveSearchQuery, rejectSearchQuery } from "@/lib/firewall"
import {
  previewMarketQuery,
  queryPurposeLabel,
  type QueryCandidateDto,
} from "@/lib/market-research"

export type QueryDecision = "pending" | "approved" | "rejected" | "blocked"

export interface ApprovalQuery extends QueryCandidateDto {
  decision: QueryDecision
}

export function toApprovalQueries(queries: QueryCandidateDto[]): ApprovalQuery[] {
  return queries.map((q) => ({
    ...q,
    decision: q.public_safe && q.approval_id ? "pending" : "blocked",
  }))
}

export function approvedIds(queries: ApprovalQuery[]): string[] {
  return queries
    .filter((q) => q.decision === "approved" && q.approval_id)
    .map((q) => q.approval_id as string)
}

const DECISION_LABELS: Record<QueryDecision, string> = {
  pending: "Offen",
  approved: "Freigegeben",
  rejected: "Abgelehnt",
  blocked: "Blockiert",
}

const DECISION_STYLE: Record<QueryDecision, string> = {
  pending: "bg-muted text-muted-foreground",
  approved: "bg-status-fulfilled/12 text-status-fulfilled",
  rejected: "bg-muted text-muted-foreground",
  blocked: "bg-destructive/10 text-destructive",
}

export function QueryApprovalList({
  projectId,
  queries,
  onChange,
}: {
  projectId: string
  queries: ApprovalQuery[]
  onChange: (next: ApprovalQuery[]) => void
}) {
  const [busyIndex, setBusyIndex] = React.useState<number | null>(null)
  const [editIndex, setEditIndex] = React.useState<number | null>(null)
  const [editText, setEditText] = React.useState("")
  const [error, setError] = React.useState<string | null>(null)

  const update = (index: number, patch: Partial<ApprovalQuery>) => {
    onChange(queries.map((q, i) => (i === index ? { ...q, ...patch } : q)))
  }

  const decide = async (index: number, approve: boolean) => {
    const query = queries[index]
    if (!query.approval_id) return
    setBusyIndex(index)
    setError(null)
    try {
      if (approve) await approveSearchQuery(query.approval_id)
      else await rejectSearchQuery(query.approval_id)
      update(index, { decision: approve ? "approved" : "rejected" })
    } catch {
      setError("Die Freigabe konnte nicht gespeichert werden. Bitte erneut versuchen.")
    } finally {
      setBusyIndex(null)
    }
  }

  const startEdit = (index: number) => {
    setEditIndex(index)
    setEditText(queries[index].query_text)
    setError(null)
  }

  const confirmEdit = async (index: number) => {
    const query = queries[index]
    setBusyIndex(index)
    setError(null)
    try {
      const next = await previewMarketQuery(projectId, editText, query.purpose)
      // Bearbeiten invalidiert die alte Freigabe explizit (die Hash-Bindung macht
      // sie ohnehin unbrauchbar für den neuen Text).
      if (query.approval_id) {
        try {
          await rejectSearchQuery(query.approval_id)
        } catch {
          // bereits entschieden/abgelaufen — die neue Freigabe zählt
        }
      }
      update(index, {
        query_text: next.query_text,
        approval_id: next.approval_id,
        public_safe: next.public_safe,
        blocked_reason: next.blocked_reason,
        decision: next.public_safe && next.approval_id ? "pending" : "blocked",
      })
      setEditIndex(null)
    } catch {
      setError("Die Suchanfrage konnte nicht geprüft werden. Bitte erneut versuchen.")
    } finally {
      setBusyIndex(null)
    }
  }

  const approvedCount = queries.filter((q) => q.decision === "approved").length

  return (
    <div className="flex flex-col gap-2" data-testid="query-approval-list">
      {error && (
        <p role="alert" className="text-xs text-destructive">
          {error}
        </p>
      )}
      <ul className="flex flex-col gap-2">
        {queries.map((query, index) => (
          <li
            key={`${query.purpose}-${index}`}
            data-testid="query-approval-row"
            className="rounded-md border border-border p-2.5"
          >
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0 flex-1">
                <p className="text-[11px] font-medium text-muted-foreground">
                  {queryPurposeLabel(query.purpose)}
                </p>
                {editIndex === index ? (
                  <div className="mt-1 flex flex-col gap-1.5">
                    <Input
                      value={editText}
                      onChange={(e) => setEditText(e.target.value)}
                      aria-label="Suchanfrage bearbeiten"
                      data-testid="query-edit-input"
                    />
                    <div className="flex gap-1.5">
                      <Button
                        type="button"
                        size="xs"
                        variant="outline"
                        disabled={busyIndex === index || !editText.trim()}
                        onClick={() => void confirmEdit(index)}
                      >
                        {busyIndex === index ? (
                          <Loader2 className="size-3 animate-spin" />
                        ) : null}
                        Prüfen und übernehmen
                      </Button>
                      <Button
                        type="button"
                        size="xs"
                        variant="ghost"
                        onClick={() => setEditIndex(null)}
                      >
                        Abbrechen
                      </Button>
                    </div>
                  </div>
                ) : (
                  <p className="mt-0.5 break-words text-sm text-foreground">
                    {query.query_text}
                  </p>
                )}
                {query.decision === "blocked" && (
                  <p className="mt-1 text-[11px] text-destructive">
                    Diese Anfrage enthält gesperrte Angaben und wird nicht
                    ausgeführt. Bitte allgemeiner formulieren.
                  </p>
                )}
              </div>
              <Badge variant="secondary" className={DECISION_STYLE[query.decision]}>
                {DECISION_LABELS[query.decision]}
              </Badge>
            </div>
            {query.decision === "pending" && editIndex !== index && (
              <div className="mt-2 flex gap-1.5">
                <Button
                  type="button"
                  size="xs"
                  variant="outline"
                  disabled={busyIndex === index}
                  onClick={() => void decide(index, true)}
                >
                  <Check className="size-3" /> Freigeben
                </Button>
                <Button
                  type="button"
                  size="xs"
                  variant="ghost"
                  disabled={busyIndex === index}
                  onClick={() => void decide(index, false)}
                >
                  <X className="size-3" /> Ablehnen
                </Button>
                <Button
                  type="button"
                  size="xs"
                  variant="ghost"
                  disabled={busyIndex === index}
                  onClick={() => startEdit(index)}
                >
                  <Pencil className="size-3" /> Bearbeiten
                </Button>
              </div>
            )}
          </li>
        ))}
      </ul>
      <p className="text-xs text-muted-foreground" data-testid="query-approval-count">
        {approvedCount} von {queries.length} Suchanfragen freigegeben
      </p>
    </div>
  )
}
