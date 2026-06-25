"use client"

import * as React from "react"
import { Download, FileText, FileCode, FileJson, Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import {
  createExport,
  downloadExport,
  type ExportArtifactDto,
  type ExportType,
} from "@/lib/exports"
import { getReview, type ApprovalStatus } from "@/lib/review"

const PAGE_DISCLAIMER =
  "Dies ist keine Einreichfreigabe. Die Einreichung erfolgt durch Sie im " +
  "Innosuisse-Portal. Diese Plattform reicht nichts automatisch ein."

const CARDS: { type: ExportType; title: string; subtitle: string; icon: typeof FileText }[] = [
  { type: "docx", title: "Word-Arbeitsdokument", subtitle: "DOCX", icon: FileText },
  { type: "markdown", title: "Markdown-Zusammenfassung", subtitle: "Markdown", icon: FileCode },
  {
    type: "technical_evidence",
    title: "Technischer Nachweis",
    subtitle: "JSON für Audit und Weiterverarbeitung",
    icon: FileJson,
  },
]

type CardState = "idle" | "creating" | "ready" | "error"

function reviewBanner(status: ApprovalStatus | null): { text: string; tone: string } {
  if (status === "approved")
    return { text: "Review freigegeben – keine Einreichfreigabe.", tone: "emerald" }
  if (status === "stale")
    return {
      text: "Die Review-Freigabe ist veraltet. Exporte werden als ENTWURF gekennzeichnet.",
      tone: "amber",
    }
  return {
    text: "Noch nicht review-freigegeben – Exporte werden als ENTWURF gekennzeichnet.",
    tone: "amber",
  }
}

export function LiveExport({ runId }: { runId: string }) {
  const [approval, setApproval] = React.useState<ApprovalStatus | null>(null)
  const [state, setState] = React.useState<Record<string, CardState>>({})
  const [artifacts, setArtifacts] = React.useState<Record<string, ExportArtifactDto>>({})
  const [errors, setErrors] = React.useState<Record<string, string>>({})

  React.useEffect(() => {
    getReview(runId)
      .then((pkg) => setApproval(pkg.approval_status))
      .catch(() => setApproval(null))
  }, [runId])

  async function create(type: ExportType) {
    setState((s) => ({ ...s, [type]: "creating" }))
    setErrors((e) => ({ ...e, [type]: "" }))
    try {
      const artifact = await createExport(runId, type)
      setArtifacts((a) => ({ ...a, [type]: artifact }))
      setState((s) => ({ ...s, [type]: "ready" }))
    } catch (e) {
      setErrors((er) => ({
        ...er,
        [type]: e instanceof Error ? e.message : "Export fehlgeschlagen.",
      }))
      setState((s) => ({ ...s, [type]: "error" }))
    }
  }

  const banner = reviewBanner(approval)
  const advisoryDraft = approval !== "approved"

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-5">
      <h1 className="text-lg font-semibold">Export</h1>

      <p
        role="status"
        className={`rounded-md border px-3 py-2 text-sm ${
          banner.tone === "emerald"
            ? "border-emerald-300 bg-emerald-50 text-emerald-900"
            : "border-amber-300 bg-amber-50 text-amber-900"
        }`}
      >
        {banner.text}
      </p>

      <div className="grid gap-4 md:grid-cols-3">
        {CARDS.map((card) => {
          const cardState = state[card.type] ?? "idle"
          const artifact = artifacts[card.type]
          // After creation, the artifact's draft_marked is authoritative.
          const draft = artifact ? artifact.draft_marked : advisoryDraft
          const Icon = card.icon
          return (
            <div
              key={card.type}
              className="flex flex-col gap-3 rounded-lg border border-border bg-card p-4"
            >
              <div className="flex items-start justify-between gap-2">
                <Icon className="size-6 text-muted-foreground" />
                {draft && <Badge variant="outline">ENTWURF</Badge>}
              </div>
              <div>
                <h2 className="text-sm font-semibold">{card.title}</h2>
                <p className="text-xs text-muted-foreground">{card.subtitle}</p>
              </div>

              {cardState === "ready" && artifact ? (
                <div className="flex flex-col gap-1">
                  <Button size="sm" onClick={() => downloadExport(artifact)}>
                    <Download data-icon="inline-start" />
                    Bereit zum Herunterladen
                  </Button>
                  <span className="truncate text-xs text-muted-foreground">
                    {artifact.filename}
                  </span>
                </div>
              ) : cardState === "creating" ? (
                <Button size="sm" disabled>
                  <Loader2 className="mr-1 size-4 animate-spin" />
                  Wird erstellt …
                </Button>
              ) : cardState === "error" ? (
                <Button size="sm" variant="outline" onClick={() => create(card.type)}>
                  Fehler – erneut versuchen
                </Button>
              ) : (
                <Button size="sm" variant="outline" onClick={() => create(card.type)}>
                  Erstellen
                </Button>
              )}
              {errors[card.type] && (
                <p role="alert" className="text-xs text-destructive">
                  {errors[card.type]}
                </p>
              )}
            </div>
          )
        })}
      </div>

      <p className="text-xs text-muted-foreground">{PAGE_DISCLAIMER}</p>
    </div>
  )
}

export function LiveExportSkeleton() {
  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-4">
      <Skeleton className="h-8 w-40" />
      <div className="grid gap-4 md:grid-cols-3">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-44 rounded-lg" />
        ))}
      </div>
    </div>
  )
}
