"use client"

import * as React from "react"
import { CheckCircle2, Loader2, Lock } from "lucide-react"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion"
import { Separator } from "@/components/ui/separator"
import {
  QueryApprovalList,
  approvedIds,
  toApprovalQueries,
  type ApprovalQuery,
} from "@/components/research/query-approval-list"
import { planMarketResearch } from "@/lib/market-research"
import { AI_REASON_INFO, FALLBACK_AI_REASON } from "@/lib/redraft"
import { expectedPhases } from "@/lib/run-steps"
import { LLMToggle, WebSearchToggle } from "./service-toggles"
import {
  isCloudAllowed,
  isWebAllowed,
  type AnalyseSettings,
  type DataClass,
  type Role,
  type ServiceAvailability,
} from "@/lib/types"
import type { Origin } from "@/lib/data-classification"

interface AnalyseEinstellungenDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  role: Role
  dataClass: DataClass
  variant?: "full" | "compact"
  serviceAvailability?: ServiceAvailability
  hasActiveRun?: boolean
  // R8 Query-Freigabe: nur mit Projekt kann der Dialog die geplanten Suchanfragen
  // laden und freigeben lassen (öffentliche Projekte, Web-Toggle an).
  projectId?: string
  projectOrigin?: Origin
  /**
   * "live" = der Dialog erstellt einen expliziten Live-Lauf
   * (processing_mode=live) mit eigener Live-Bestätigung. Default: Bestand.
   */
  intent?: "standard" | "live"
  onStart?: (settings: AnalyseSettings) => void
  onCancel?: () => void
}

const dataClassLabel: Record<DataClass, string> = {
  public: "Öffentlich",
  internal: "Intern",
  confidential: "Vertraulich",
  nda: "NDA / gesperrt",
}

export function AnalyseEinstellungenDialog({
  open,
  onOpenChange,
  role,
  dataClass,
  variant = "full",
  serviceAvailability = { ki: true, web: true, generationMode: "real_eval" },
  hasActiveRun = false,
  projectId,
  projectOrigin = "synthetic",
  intent = "standard",
  onStart,
  onCancel,
}: AnalyseEinstellungenDialogProps) {
  // Ein realer Modelllauf ist für synthetische/anonymisierte Evaluationsfälle
  // sowie — Demo-Slice 2026-07-17 — für öffentliche public_source-Projekte
  // verfügbar (spiegelt das Backend-Live-Gate). FakeProvider ist ein
  // Demo-Pfad, kein lokaler/institutioneller Modelladapter.
  const intentLive = intent === "live"
  const isLocalOnlyClass = !isCloudAllowed(dataClass)
  const evaluationOrigin = projectOrigin === "synthetic" || projectOrigin === "anonymized"
  const liveEligibleOrigin =
    evaluationOrigin ||
    (projectOrigin === "public_source" && dataClass === "public")
  const realEvaluation =
    serviceAvailability.generationMode === "real_eval" && liveEligibleOrigin
  const demoMode =
    serviceAvailability.generationMode === "fake_demo" && evaluationOrigin
  const aiAvailable = serviceAvailability.ki && (realEvaluation || demoMode)
  const [ki, setKi] = React.useState(aiAvailable)
  // Live-Intent: die KI-Unterstützung ist der Zweck des Dialogs — beim Öffnen
  // einschalten, sobald sie verfügbar ist (Capabilities können nachladen).
  React.useEffect(() => {
    if (open && intentLive && aiAvailable) setKi(true)
  }, [open, intentLive, aiAvailable])
  const [web, setWeb] = React.useState(false) // DEFAULT OFF always
  const [costLimit, setCostLimit] = React.useState("2.00")
  // Erweiterte Einstellungen (nur lead_admin) — echte, gesendete Limits.
  const [maxLlmCalls, setMaxLlmCalls] = React.useState("25")
  const [maxWebCalls, setMaxWebCalls] = React.useState("5")
  // Reale Modellaufrufe erfordern eine einmalige Bestätigung pro Run.
  const [cloudConfirmed, setCloudConfirmed] = React.useState(false)

  const webDisabled = !isWebAllowed(dataClass)
  const effectiveWeb = web && !webDisabled

  // A4 — jeder deaktivierte Schalter erklärt exakt warum. Reihenfolge: die
  // speziellste Ursache gewinnt (NDA → Datenklasse → Provider → Projektherkunft).
  // Die Texte unterscheiden sich bewusst vom Datenklassen-Banner, damit beide
  // gleichzeitig lesbar bleiben.
  let kiUnavailableReason: string | undefined
  if (!aiAvailable) {
    if (dataClass === "nda") {
      kiUnavailableReason = AI_REASON_INFO.nda_locked.text
    } else if (isLocalOnlyClass) {
      kiUnavailableReason = `Für die Vertraulichkeitsstufe «${dataClassLabel[dataClass]}» ist kein KI-Provider freigegeben — es laufen nur regelbasierte Prüfungen.`
    } else if (
      !serviceAvailability.ki ||
      serviceAvailability.generationMode === "unavailable" ||
      serviceAvailability.generationMode === "live_unavailable" ||
      !serviceAvailability.generationMode
    ) {
      const reasonCode = serviceAvailability.unavailableReason
      kiUnavailableReason =
        (reasonCode ? AI_REASON_INFO[reasonCode]?.text : undefined) ??
        AI_REASON_INFO[FALLBACK_AI_REASON].text
    } else if (!liveEligibleOrigin) {
      kiUnavailableReason =
        "Nur für öffentliche, synthetische oder anonymisierte Fälle verfügbar — dieses Projekt enthält echte, nicht-öffentliche Projektdaten."
    }
  }
  let webUnavailableReason: string | undefined
  if (webDisabled) {
    webUnavailableReason = `Nur bei Vertraulichkeitsstufe «Öffentlich» verfügbar — aktuelle Stufe: ${dataClassLabel[dataClass]}.`
  } else if (!serviceAvailability.web) {
    webUnavailableReason = "Die öffentliche Websuche ist serverseitig deaktiviert."
  }
  // Der Demo-Pfad nutzt aus Kompatibilitätsgründen denselben Run-Modus, ruft
  // aber keinen Provider auf. Die Bestätigung benennt das ausdrücklich.
  const cloudOptIn = ki && (realEvaluation || demoMode)
  // Block the start until the user confirms AI processing for this run.
  const cloudConfirmationMissing = cloudOptIn && !cloudConfirmed
  // Live-Intent: ohne aktivierte und bestätigte Live-KI gibt es keinen
  // Live-Lauf — nie ein stiller Rückfall auf regelbasierte Verarbeitung.
  const liveStartBlocked =
    intentLive && !(ki && aiAvailable && realEvaluation && cloudConfirmed)

  // R8 Query-Freigabe: geplante Suchanfragen laden, sobald die Webrecherche für ein
  // öffentliches Projekt aktiviert wird. Ohne Freigaben wird die Recherche-Phase im
  // Lauf ehrlich übersprungen — der Start bleibt möglich.
  const canApproveQueries =
    effectiveWeb && dataClass === "public" && Boolean(projectId)
  const [webQueries, setWebQueries] = React.useState<ApprovalQuery[] | null>(null)
  const [webQueriesLoading, setWebQueriesLoading] = React.useState(false)
  const [webQueriesError, setWebQueriesError] = React.useState<string | null>(null)
  const [webQueriesReload, setWebQueriesReload] = React.useState(0)

  React.useEffect(() => {
    if (!open || !canApproveQueries || !projectId) {
      setWebQueries(null)
      setWebQueriesError(null)
      return
    }
    let cancelled = false
    setWebQueries(null)
    setWebQueriesError(null)
    setWebQueriesLoading(true)
    planMarketResearch(projectId)
      .then((plan) => {
        if (!cancelled) setWebQueries(toApprovalQueries(plan.queries))
      })
      .catch(() => {
        if (!cancelled)
          setWebQueriesError(
            "Die Suchanfragen konnten nicht geladen werden. Ohne Freigabe wird die Webrecherche übersprungen."
          )
      })
      .finally(() => {
        if (!cancelled) setWebQueriesLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [open, canApproveQueries, projectId, webQueriesReload])

  function handleStart() {
    onStart?.({
      ki: ki && aiAvailable,
      web: effectiveWeb,
      localSourcesOnly: false,
      costLimit: Number.parseFloat(costLimit) || 0,
      // Beta: Modell-Routing ist eine Backend-/Config-Entscheidung —
      // die Drafter/Critic-Trennung bleibt cross-provider.
      model: "auto",
      maxLlmCalls: Number.parseInt(maxLlmCalls, 10) || 25,
      maxWebCalls: Number.parseInt(maxWebCalls, 10) || 5,
      cloudConfirmed: cloudOptIn && cloudConfirmed,
      liveRun: intentLive,
    })
  }

  function handleCancel() {
    onCancel?.()
    onOpenChange(false)
  }

  // Volle Konfiguration als breites Side-Sheet (Desktop ≥880 px, 85 vw, Cap
  // 1000 px); Aktiv-Lauf- und Kompaktansicht bleiben schmal. Die Overrides
  // sind varianten-identisch zu den Sheet-Defaults (data-[side=right]:…),
  // damit tailwind-merge die eingebauten w-3/4 / sm:max-w-sm sicher ersetzt.
  const fullConfig = !hasActiveRun && variant !== "compact"
  const widthClasses = fullConfig
    ? "data-[side=right]:w-full data-[side=right]:sm:w-[85vw] data-[side=right]:sm:min-w-[880px] data-[side=right]:sm:max-w-[1000px]"
    : "data-[side=right]:w-full data-[side=right]:sm:max-w-md"

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        className={`flex flex-col gap-0 overflow-hidden p-0 ${widthClasses}`}
      >
        <SheetHeader className="shrink-0 border-b border-border px-6 py-4">
          <SheetTitle>
            {intentLive ? "Neuen Live-Lauf erstellen" : "Analyse starten"}
          </SheetTitle>
          <SheetDescription>
            {intentLive
              ? "Prüfen Sie die Einstellungen für diesen Live-Durchlauf mit echter KI."
              : "Prüfen Sie kurz die Einstellungen für diesen Durchlauf."}
          </SheetDescription>
        </SheetHeader>

        {hasActiveRun ? (
          <ActiveRunBody onClose={handleCancel} />
        ) : variant === "compact" ? (
          <CompactBody available={serviceAvailability.ki} />
        ) : (
          <div className="flex min-w-0 flex-1 flex-col gap-5 overflow-y-auto px-6 py-5 lg:grid lg:grid-cols-2 lg:content-start lg:gap-x-10">
            <div className="flex min-w-0 flex-col gap-5">
            {/* Immer Teil des Durchlaufs: die Analyse der Projektunterlagen. */}
            <div className="flex items-start justify-between gap-4">
              <div className="flex flex-col gap-1">
                <span className="text-sm font-medium text-foreground">
                  Projektunterlagen analysieren
                </span>
                <p className="text-xs text-muted-foreground">
                  Ihre Unterlagen und Angaben werden geprüft; daraus entstehen
                  formale Prüfergebnisse und Textvorschläge zur menschlichen
                  Prüfung.
                </p>
              </div>
              <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <CheckCircle2 className="size-4 text-status-fulfilled" />
                aktiviert
              </span>
            </div>

            {/* Local-only class banner */}
            {isLocalOnlyClass && !realEvaluation && !demoMode && (
              <div className="flex items-start gap-2 rounded-md border border-border bg-muted/50 p-3 text-sm text-muted-foreground">
                <Lock className="mt-0.5 size-4 shrink-0" />
                <span>
                  Für diese Datenklasse ist aktuell kein freigegebener KI-Provider
                  konfiguriert. Die App führt nur regelbasierte Prüfungen aus.
                </span>
              </div>
            )}

            <LLMToggle
              id="ki-toggle"
              checked={ki}
              onCheckedChange={setKi}
              available={
                aiAvailable
              }
              generationMode={serviceAvailability.generationMode}
              unavailableReason={kiUnavailableReason}
            />

            {/* Cloud-KI one-run confirmation (public/synthetic only) */}
            {cloudOptIn && (
              <div className="flex flex-col gap-2 rounded-md border border-border bg-muted/40 p-3 text-sm">
                <p className="font-medium text-foreground">
                  {intentLive && realEvaluation
                    ? "Live-Lauf mit echter KI"
                    : realEvaluation
                      ? "Evaluationsfall – keine echten vertraulichen Daten"
                      : "Demo-Vorschlag (kein echtes KI-Modell)"}
                </p>
                <p className="text-muted-foreground">
                  {intentLive && realEvaluation
                    ? "Echte KI-Modelle dürfen nur für diesen ausdrücklich bestätigten öffentlichen oder verlässlich anonymisierten Fall aufgerufen werden."
                    : realEvaluation
                      ? "Ein reales Modell darf nur für diesen ausdrücklich bestätigten synthetischen oder anonymisierten Evaluationsfall aufgerufen werden."
                      : "Der Demo-Generator erstellt klar gekennzeichnete Testausgaben und ruft keinen KI-Provider auf."}
                </p>
                {realEvaluation && (
                  <p className="text-muted-foreground">
                    Ausgewählte Inhalte können an den konfigurierten KI-Dienst
                    übermittelt werden. ProviderPolicy und Datenklassifikation werden
                    zusätzlich im Backend geprüft.
                  </p>
                )}
                <label className="flex items-start gap-2">
                  <Checkbox
                    checked={cloudConfirmed}
                    onCheckedChange={(c) => setCloudConfirmed(c === true)}
                    className="mt-0.5"
                    aria-label={
                      intentLive && realEvaluation
                        ? "Live-KI für diesen Durchlauf erlauben"
                        : realEvaluation
                          ? "Reale KI für diesen Evaluationsdurchlauf erlauben"
                          : "Demo-Generator für diesen Durchlauf aktivieren"
                    }
                  />
                  <span className="flex flex-col gap-0.5">
                    <span className="font-medium text-foreground">
                      {intentLive && realEvaluation
                        ? "Live-KI für diesen Durchlauf erlauben"
                        : realEvaluation
                          ? "Reale KI für diesen Evaluationsdurchlauf erlauben"
                          : "Demo-Generator für diesen Durchlauf aktivieren"}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {realEvaluation
                        ? "Ich bestätige, dass dieser Fall ausschließlich synthetische, anonymisierte oder öffentliche Inhalte enthält und für diesen Durchlauf an den konfigurierten KI-Dienst übermittelt werden darf."
                        : "Ich bestätige, dass dieser Demo-Lauf keine reale KI-Leistung darstellt."}
                    </span>
                  </span>
                </label>
              </div>
            )}

            <WebSearchToggle
              id="web-toggle"
              checked={effectiveWeb}
              onCheckedChange={setWeb}
              available={serviceAvailability.web && isWebAllowed(dataClass)}
              disabled={webDisabled}
              unavailableReason={webUnavailableReason}
            />

            {/* R8 — jede ausgehende Suchanfrage wird gesehen und freigegeben. */}
            {canApproveQueries && projectId && (
              <div className="flex flex-col gap-2 rounded-md border border-border bg-muted/40 p-3">
                <p className="text-sm font-medium text-foreground">
                  Suchanfragen für die Webrecherche
                </p>
                <p className="text-xs text-muted-foreground">
                  Diese abstrahierten Suchanfragen würden an die öffentliche
                  Websuche gesendet. Geben Sie frei, was gesendet werden darf —
                  Sie können jede Anfrage auch bearbeiten oder ablehnen.
                </p>
                {webQueriesLoading && (
                  <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
                    <Loader2 className="size-3.5 animate-spin" /> Suchanfragen
                    werden vorbereitet …
                  </p>
                )}
                {webQueriesError && (
                  <div className="flex flex-col gap-1.5">
                    <p role="alert" className="text-xs text-destructive">
                      {webQueriesError}
                    </p>
                    <Button
                      type="button"
                      size="xs"
                      variant="outline"
                      className="self-start"
                      onClick={() => setWebQueriesReload((t) => t + 1)}
                    >
                      Erneut laden
                    </Button>
                  </div>
                )}
                {webQueries && (
                  <>
                    <QueryApprovalList
                      projectId={projectId}
                      queries={webQueries}
                      onChange={setWebQueries}
                    />
                    {approvedIds(webQueries).length === 0 && (
                      <p className="text-xs text-muted-foreground">
                        Die Webrecherche wird übersprungen, bis mindestens eine
                        Suchanfrage freigegeben ist.
                      </p>
                    )}
                  </>
                )}
              </div>
            )}

            </div>

            <Separator className="lg:hidden" />

            <div className="flex min-w-0 flex-col gap-5">
            <div className="flex flex-col gap-1.5">
              <label
                htmlFor="cost-limit"
                className="text-sm font-medium text-foreground"
              >
                Kostenlimit für diesen Durchlauf
              </label>
              <div className="flex items-center gap-2">
                <span className="text-sm text-muted-foreground">CHF</span>
                <Input
                  id="cost-limit"
                  type="number"
                  step="0.01"
                  value={costLimit}
                  onChange={(e) => setCostLimit(e.target.value)}
                  className="w-32"
                />
              </div>
              <p className="text-xs text-muted-foreground">
                Beim Erreichen stoppt der Durchlauf automatisch. Dieser Schutz
                lässt sich nicht abschalten.
              </p>
            </div>

            <div className="flex flex-col gap-1.5">
              <span className="text-sm font-medium text-foreground">
                Vertraulichkeitsstufe
              </span>
              <div className="flex items-center gap-2">
                <span className="inline-flex items-center rounded-full bg-secondary px-2.5 py-0.5 text-xs font-medium text-secondary-foreground">
                  {dataClassLabel[dataClass]}
                </span>
                <span className="text-xs text-muted-foreground">
                  Bestimmt, welche Dienste genutzt werden dürfen.
                </span>
              </div>
            </div>

            {/* A2 — erwartete Phasen aus dem echten Phasenkatalog, mit ehrlich
                angekündigten Skips. Keine Dauer-/Kostenprognose. */}
            <div className="flex flex-col gap-1.5">
              <span className="text-sm font-medium text-foreground">
                Erwartete Phasen
              </span>
              <ol className="flex flex-col gap-1" data-testid="expected-phases">
                {expectedPhases({
                  ki: ki && aiAvailable,
                  web: effectiveWeb,
                  approvedQueryCount: webQueries
                    ? approvedIds(webQueries).length
                    : null,
                }).map((phase, index) => (
                  <li
                    key={phase.key}
                    className="flex items-baseline gap-2 text-xs"
                  >
                    <span className="tabular-nums text-muted-foreground/70">
                      {index + 1}.
                    </span>
                    <span className="text-foreground">{phase.label}</span>
                    {phase.note && (
                      <span className="text-muted-foreground">
                        — {phase.note}
                      </span>
                    )}
                  </li>
                ))}
              </ol>
              <p className="text-xs text-muted-foreground">
                Die Dauer hängt vom Umfang der Unterlagen ab — der Fortschritt
                ist während der Analyse Schritt für Schritt sichtbar. Die Kosten
                sind durch das Limit oben begrenzt.
              </p>
            </div>

            {/* Tier 2 — only for lead_admin */}
            {role === "lead_admin" && (
              <Accordion className="border-t border-border pt-1">
                <AccordionItem value="advanced">
                  <AccordionTrigger className="text-sm font-medium">
                    Erweiterte Einstellungen
                  </AccordionTrigger>
                  <AccordionContent>
                    <div className="flex flex-col gap-4 pt-1">
                      {/* Beta: keine Provider-Auswahl — Routing macht das System. */}
                      <p className="text-sm text-muted-foreground">
                        Modellwahl: automatisch durch das System
                      </p>
                      <div className="flex flex-col gap-1.5">
                        <label
                          htmlFor="max-llm-calls"
                          className="text-sm font-medium text-foreground"
                        >
                          Max. KI-Aufrufe pro Durchlauf
                        </label>
                        <Input
                          id="max-llm-calls"
                          type="number"
                          value={maxLlmCalls}
                          onChange={(e) => setMaxLlmCalls(e.target.value)}
                          className="w-32"
                        />
                        <p className="text-xs text-muted-foreground">
                          Begrenzt die Zahl der KI-Aufrufe; beim Erreichen werden
                          weitere Vorschläge übersprungen.
                        </p>
                      </div>
                      <div className="flex flex-col gap-1.5">
                        <label
                          htmlFor="max-web-calls"
                          className="text-sm font-medium text-foreground"
                        >
                          Max. Suchanfragen (Webrecherche)
                        </label>
                        <Input
                          id="max-web-calls"
                          type="number"
                          value={maxWebCalls}
                          onChange={(e) => setMaxWebCalls(e.target.value)}
                          disabled={!effectiveWeb}
                          className="w-32"
                        />
                        <p className="text-xs text-muted-foreground">
                          {effectiveWeb
                            ? "Begrenzt die Zahl der öffentlichen Suchanfragen."
                            : "Verfügbar, sobald die öffentliche Webrecherche aktiviert ist."}
                        </p>
                      </div>
                    </div>
                  </AccordionContent>
                </AccordionItem>
              </Accordion>
            )}
            </div>
          </div>
        )}

        {!hasActiveRun && (
          <SheetFooter className="shrink-0 flex-row items-center justify-end gap-2 border-t border-border px-6 py-4">
            {cloudConfirmationMissing ? (
              <p className="mr-auto text-xs text-muted-foreground">
                Bitte bestätigen Sie die Verarbeitung für diesen Durchlauf.
              </p>
            ) : liveStartBlocked ? (
              <p className="mr-auto text-xs text-muted-foreground">
                Für einen Live-Lauf muss die Live-KI verfügbar, aktiviert und
                bestätigt sein.
              </p>
            ) : null}
            <Button variant="outline" onClick={handleCancel}>
              Abbrechen
            </Button>
            <Button
              onClick={handleStart}
              disabled={cloudConfirmationMissing || liveStartBlocked}
            >
              {intentLive ? "Live-Lauf starten" : "Analyse starten"}
            </Button>
          </SheetFooter>
        )}
      </SheetContent>
    </Sheet>
  )
}

function ActiveRunBody({ onClose }: { onClose: () => void }) {
  return (
    <div className="flex flex-col gap-4 px-6 py-5">
      <p className="text-sm text-muted-foreground">
        Eine Analyse läuft bereits. Pro Antrag ist ein Durchlauf gleichzeitig
        möglich.
      </p>
      <SheetFooter className="p-0">
        <Button onClick={onClose}>Schließen</Button>
      </SheetFooter>
    </div>
  )
}

function CompactBody({ available }: { available: boolean }) {
  return (
    <div className="flex flex-col gap-4 px-6 py-5">
      <span className="flex items-center gap-1.5 text-sm">
        <span
          className={`size-2 rounded-full ${available ? "bg-status-fulfilled" : "bg-muted-foreground/40"}`}
        />
        <span className="text-muted-foreground">
          {available ? "KI-Unterstützung verfügbar" : "Dienst aktuell nicht verfügbar"}
        </span>
      </span>
      <p className="text-sm text-muted-foreground">
        Der automatische Kostenstopp schützt Ihr Limit für diesen Durchlauf.
      </p>
    </div>
  )
}
