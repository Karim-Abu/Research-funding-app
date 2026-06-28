"use client"

import * as React from "react"
import {
  Download,
  FileText,
  FileCode,
  FileJson,
  Loader2,
  ClipboardCopy,
  Info,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { cn } from "@/lib/utils"
import {
  createExport,
  downloadExport,
  type ExportArtifactDto,
  type ExportType,
} from "@/lib/exports"
import { getReview, type ApprovalStatus, type ReviewPackageDto } from "@/lib/review"
import { listFields, type PortalFieldDraftDto } from "@/lib/fields"
import { PortalTransfer } from "@/components/portal-transfer/portal-transfer"
import {
  EXPORT_REVIEW_LABELS,
  EXPORT_REVIEW_STYLE,
  NO_AUTO_SUBMIT_NOTE,
  summarizeExportReadiness,
} from "@/lib/export-view"

const PAGE_DISCLAIMER =
  "Dies ist keine Einreichfreigabe. Die Einreichung erfolgt durch Sie im " +
  "Innosuisse-Portal. Diese Plattform reicht nichts automatisch ein."

const CARDS: {
  type: ExportType
  title: string
  subtitle: string
  icon: typeof FileText
  recommended?: boolean
}[] = [
  {
    type: "docx",
    title: "Word-Arbeitsdokument",
    subtitle: "Editierbares Arbeitsdokument pro Portalabschnitt zur Weiterbearbeitung im Antragsteam.",
    icon: FileText,
    recommended: true,
  },
  {
    type: "markdown",
    title: "Markdown-Zusammenfassung",
    subtitle: "Kompakte textbasierte Übersicht für Dokumentation oder interne Notizen.",
    icon: FileCode,
  },
  {
    type: "technical_evidence",
    title: "Technischer Nachweis",
    subtitle: "Strukturierte Daten mit Evidenz, Status und Prüfinformationen für Audit und Evaluation.",
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
  const [pkg, setPkg] = React.useState<ReviewPackageDto | null>(null)
  const [approval, setApproval] = React.useState<ApprovalStatus | null>(null)
  const [state, setState] = React.useState<Record<string, CardState>>({})
  const [artifacts, setArtifacts] = React.useState<Record<string, ExportArtifactDto>>({})
  const [errors, setErrors] = React.useState<Record<string, string>>({})
  const [tab, setTab] = React.useState<"optionen" | "innolink">("optionen")
  const [fields, setFields] = React.useState<PortalFieldDraftDto[] | null>(null)

  React.useEffect(() => {
    getReview(runId)
      .then((p) => {
        setPkg(p)
        setApproval(p.approval_status)
      })
      .catch(() => {
        setPkg(null)
        setApproval(null)
      })
  }, [runId])

  function openInnolink() {
    setTab("innolink")
    if (fields === null) {
      listFields(runId).then(setFields).catch(() => setFields([]))
    }
  }

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
  const readiness = summarizeExportReadiness(pkg)
  const hint =
    readiness.reviewStatus === "nicht_durchgefuehrt"
      ? "Es wurde noch keine Qualitätsprüfung durchgeführt. Exporte werden als Entwurf gekennzeichnet."
      : readiness.reviewStatus === "blockiert"
        ? "Der Antrag enthält noch blockierende Punkte. Prüfen Sie diese vor dem Export."
        : "Der Antrag ist bereit für den Export. Bitte prüfen Sie die Inhalte final vor der Verwendung."

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-5">
      <div className="flex flex-col gap-1">
        <h1 className="text-balance text-2xl font-semibold text-foreground">Export</h1>
        <p className="text-sm text-muted-foreground">
          Erstellen Sie ein editierbares Arbeitsdokument oder übernehmen Sie
          geprüfte Feldinhalte manuell nach Innolink.
        </p>
      </div>

      <Tabs
        value={tab}
        onValueChange={(v) => (v === "innolink" ? openInnolink() : setTab("optionen"))}
      >
        <TabsList>
          <TabsTrigger value="optionen">Exportoptionen</TabsTrigger>
          <TabsTrigger value="innolink">Innolink-Kopieransicht</TabsTrigger>
        </TabsList>

        <TabsContent value="optionen" className="mt-4 flex flex-col gap-5">
          {/* Status card */}
          <section className="flex flex-col gap-3 rounded-lg border border-border bg-card px-5 py-4">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-medium text-foreground">Qualitätsprüfung</span>
              <span
                className={cn(
                  "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
                  EXPORT_REVIEW_STYLE[readiness.reviewStatus]
                )}
              >
                {EXPORT_REVIEW_LABELS[readiness.reviewStatus]}
              </span>
            </div>
            <dl className="grid grid-cols-3 gap-3 text-center">
              <div className="rounded-md border border-border px-2 py-2">
                <dd className={cn("text-lg font-semibold", readiness.blockerCount > 0 && "text-destructive")}>
                  {readiness.blockerCount}
                </dd>
                <dt className="text-[11px] text-muted-foreground">Blocker</dt>
              </div>
              <div className="rounded-md border border-border px-2 py-2">
                <dd className="text-lg font-semibold text-status-fulfilled">{readiness.fieldsReady}</dd>
                <dt className="text-[11px] text-muted-foreground">Felder bereit</dt>
              </div>
              <div className="rounded-md border border-border px-2 py-2">
                <dd className="text-lg font-semibold text-foreground">{readiness.fieldsOpen}</dd>
                <dt className="text-[11px] text-muted-foreground">Offene Punkte</dt>
              </div>
            </dl>
            <p className="text-sm text-muted-foreground">{hint}</p>
            <p
              role="status"
              className={cn(
                "rounded-md border px-3 py-2 text-sm",
                banner.tone === "emerald"
                  ? "border-emerald-300 bg-emerald-50 text-emerald-900"
                  : "border-amber-300 bg-amber-50 text-amber-900"
              )}
            >
              {banner.text}
            </p>
          </section>

          {/* Export cards */}
          <div className="grid gap-4 md:grid-cols-3">
            {CARDS.map((card) => {
              const cardState = state[card.type] ?? "idle"
              const artifact = artifacts[card.type]
              const draft = artifact ? artifact.draft_marked : advisoryDraft
              const Icon = card.icon
              return (
                <div
                  key={card.type}
                  className={cn(
                    "flex flex-col gap-3 rounded-lg border bg-card p-4",
                    card.recommended ? "border-primary/40 ring-1 ring-primary/10" : "border-border"
                  )}
                >
                  <div className="flex items-start justify-between gap-2">
                    <Icon className="size-6 text-muted-foreground" />
                    <div className="flex flex-col items-end gap-1">
                      {card.recommended && (
                        <Badge className="bg-primary/10 text-primary">Empfohlen</Badge>
                      )}
                      {draft && <Badge variant="outline">ENTWURF</Badge>}
                    </div>
                  </div>
                  <div>
                    <h2 className="text-sm font-semibold">{card.title}</h2>
                    <p className="text-xs text-muted-foreground">{card.subtitle}</p>
                  </div>

                  {cardState === "ready" && artifact ? (
                    <div className="mt-auto flex flex-col gap-1">
                      <Button size="sm" onClick={() => downloadExport(artifact)}>
                        <Download data-icon="inline-start" />
                        Bereit zum Herunterladen
                      </Button>
                      <span className="truncate text-xs text-muted-foreground">
                        {artifact.filename}
                      </span>
                    </div>
                  ) : cardState === "creating" ? (
                    <Button size="sm" className="mt-auto" disabled>
                      <Loader2 className="mr-1 size-4 animate-spin" />
                      Wird erstellt …
                    </Button>
                  ) : cardState === "error" ? (
                    <Button size="sm" variant="outline" className="mt-auto" onClick={() => create(card.type)}>
                      Fehler – erneut versuchen
                    </Button>
                  ) : (
                    <Button size="sm" variant="outline" className="mt-auto" onClick={() => create(card.type)}>
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

          {/* Innolink copy view — opens the assistant; creates no export. */}
          <button
            type="button"
            onClick={openInnolink}
            className="flex items-center gap-3 rounded-lg border border-border bg-card p-4 text-left transition-colors hover:bg-accent/50"
          >
            <ClipboardCopy className="size-6 text-muted-foreground" />
            <div className="flex-1">
              <h2 className="text-sm font-semibold">Innolink-Kopieransicht</h2>
              <p className="text-xs text-muted-foreground">
                Feldweise Inhalte prüfen und manuell in das Innolink-Portal kopieren.
              </p>
            </div>
            <span className="shrink-0 rounded-full border border-border px-2 py-0.5 text-[11px] text-muted-foreground">
              Hilfsansicht
            </span>
          </button>

          <p className="text-xs text-muted-foreground">{PAGE_DISCLAIMER}</p>
        </TabsContent>

        <TabsContent value="innolink" className="mt-4 flex flex-col gap-4">
          <p className="flex items-start gap-2 rounded-md border border-border bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
            <Info className="mt-0.5 size-4 shrink-0" />
            {NO_AUTO_SUBMIT_NOTE}
          </p>
          {fields === null ? (
            <div className="flex flex-col gap-3">
              {[0, 1, 2].map((i) => (
                <Skeleton key={i} className="h-28 w-full rounded-lg" />
              ))}
            </div>
          ) : (
            <PortalTransfer fields={fields} review={pkg} embedded />
          )}
        </TabsContent>
      </Tabs>
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
