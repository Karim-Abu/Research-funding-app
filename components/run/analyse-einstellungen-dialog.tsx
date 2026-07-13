"use client"

import * as React from "react"
import { CheckCircle2, Loader2, Lock } from "lucide-react"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
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
import { LLMToggle, WebSearchToggle } from "./service-toggles"
import {
  isCloudAllowed,
  isWebAllowed,
  type AnalyseSettings,
  type DataClass,
  type Role,
  type ServiceAvailability,
} from "@/lib/types"

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
  serviceAvailability = { ki: true, web: true },
  hasActiveRun = false,
  projectId,
  onStart,
  onCancel,
}: AnalyseEinstellungenDialogProps) {
  // Beta-Policy: public darf validierte externe Dienste nutzen. R4.3 (Owner-
  // Entscheid 2026-07-08): intern/vertraulich erhalten KI nur über den lokalen
  // Verarbeitungspfad nach manuellem Opt-in + verstandener Warnung; NDA und
  // unklassifiziert bleiben vollständig blockiert.
  const isLocalOnlyClass = !isCloudAllowed(dataClass)
  const localOptInClass = dataClass === "internal" || dataClass === "confidential"

  const [ki, setKi] = React.useState(!isLocalOnlyClass)
  const [web, setWeb] = React.useState(false) // DEFAULT OFF always
  const [costLimit, setCostLimit] = React.useState("2.00")
  // Erweiterte Einstellungen (nur lead_admin) — echte, gesendete Limits.
  const [maxLlmCalls, setMaxLlmCalls] = React.useState("25")
  const [maxWebCalls, setMaxWebCalls] = React.useState("5")
  // KI requires an explicit one-run acknowledgement (cloud: public/synthetic;
  // lokal: D1/D2 mit Warnung).
  const [cloudConfirmed, setCloudConfirmed] = React.useState(false)

  const webDisabled = !isWebAllowed(dataClass)
  const effectiveWeb = web && !webDisabled
  const cloudOptIn = ki && !isLocalOnlyClass
  const localOptIn = ki && localOptInClass
  // Block the start until the user confirms AI processing for this run.
  const cloudConfirmationMissing = (cloudOptIn || localOptIn) && !cloudConfirmed

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
      ki: cloudOptIn || localOptIn,
      web: effectiveWeb,
      localSourcesOnly: false,
      costLimit: Number.parseFloat(costLimit) || 0,
      // Beta: Modell-Routing ist eine Backend-/Config-Entscheidung —
      // die Drafter/Critic-Trennung bleibt cross-provider.
      model: "auto",
      maxLlmCalls: Number.parseInt(maxLlmCalls, 10) || 25,
      maxWebCalls: Number.parseInt(maxWebCalls, 10) || 5,
      cloudConfirmed: (cloudOptIn || localOptIn) && cloudConfirmed,
    })
  }

  function handleCancel() {
    onCancel?.()
    onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-h-[90dvh] max-w-[560px] flex-col overflow-hidden">
        <DialogHeader className="shrink-0">
          <DialogTitle>Analyse starten</DialogTitle>
          <DialogDescription>
            Prüfen Sie kurz die Einstellungen für diesen Durchlauf.
          </DialogDescription>
        </DialogHeader>

        {hasActiveRun ? (
          <ActiveRunBody onClose={handleCancel} />
        ) : variant === "compact" ? (
          <CompactBody available={serviceAvailability.ki} />
        ) : (
          <div className="flex flex-col gap-5 overflow-y-auto py-1 pr-1">
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
            {isLocalOnlyClass && (
              <div className="flex items-start gap-2 rounded-md border border-border bg-muted/50 p-3 text-sm text-muted-foreground">
                <Lock className="mt-0.5 size-4 shrink-0" />
                {localOptInClass
                  ? "Externe KI- und Webdienste sind für diese Vertraulichkeitsstufe deaktiviert. KI-Unterstützung ist nur über den freigegebenen lokalen Verarbeitungspfad möglich und muss unten bewusst freigegeben werden."
                  : "Für NDA-geschützte oder gesperrte Inhalte werden keine KI- oder Webdienste verwendet."}
              </div>
            )}

            <LLMToggle
              id="ki-toggle"
              checked={ki}
              onCheckedChange={setKi}
              available={
                serviceAvailability.ki && (!isLocalOnlyClass || localOptInClass)
              }
            />

            {/* Cloud-KI one-run confirmation (public/synthetic only) */}
            {cloudOptIn && (
              <div className="flex flex-col gap-2 rounded-md border border-border bg-muted/40 p-3 text-sm">
                <p className="text-muted-foreground">
                  Cloud-KI kann für diesen Durchlauf bewusst freigegeben werden,
                  sofern die Daten öffentlich oder synthetisch sind.
                </p>
                <p className="text-muted-foreground">
                  Cloud-KI kann ausgewählte Inhalte an den konfigurierten
                  KI-Dienst übermitteln. Diese Beta erlaubt Cloud-KI nur für
                  öffentliche oder synthetische Inhalte. Interne, vertrauliche
                  oder NDA-Inhalte werden blockiert.
                </p>
                <label className="flex items-start gap-2">
                  <Checkbox
                    checked={cloudConfirmed}
                    onCheckedChange={(c) => setCloudConfirmed(c === true)}
                    className="mt-0.5"
                    aria-label="Cloud-KI für diesen Durchlauf erlauben"
                  />
                  <span className="flex flex-col gap-0.5">
                    <span className="font-medium text-foreground">
                      Cloud-KI für diesen Durchlauf erlauben
                    </span>
                    <span className="text-xs text-muted-foreground">
                      Ich bestätige, dass die ausgewählten Inhalte öffentlich
                      oder synthetisch sind und für diesen Durchlauf an den
                      konfigurierten KI-Dienst übermittelt werden dürfen.
                    </span>
                  </span>
                </label>
              </div>
            )}

            {/* R4.3 — lokaler KI-Opt-in für intern/vertraulich: deutliche
                Warnung + Verstanden-Bestätigung (Owner-Entscheid 2026-07-08) */}
            {localOptIn && (
              <div
                data-testid="local-ai-warning"
                className="flex flex-col gap-2 rounded-md border border-status-partial/40 bg-status-partial/8 p-3 text-sm"
              >
                <p className="font-medium text-foreground">
                  Warnung: KI-Unterstützung für{" "}
                  {dataClass === "internal" ? "interne" : "vertrauliche"} Inhalte
                </p>
                <p className="text-muted-foreground">
                  Die Verarbeitung erfolgt ausschliesslich über den freigegebenen
                  lokalen Verarbeitungspfad — Inhalte werden nicht an externe
                  KI-Dienste übermittelt. KI-Vorschläge werden nie automatisch
                  übernommen; prüfen Sie Ergebnisse immer fachlich, bevor Sie sie
                  verwenden.
                </p>
                <label className="flex items-start gap-2">
                  <Checkbox
                    checked={cloudConfirmed}
                    onCheckedChange={(c) => setCloudConfirmed(c === true)}
                    className="mt-0.5"
                    aria-label="KI-Unterstützung für diesen Durchlauf freigeben"
                  />
                  <span className="flex flex-col gap-0.5">
                    <span className="font-medium text-foreground">
                      Ich habe die Warnung verstanden
                    </span>
                    <span className="text-xs text-muted-foreground">
                      Ich gebe die KI-Unterstützung über den lokalen
                      Verarbeitungspfad für diesen Durchlauf bewusst frei.
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

            <Separator />

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

            {/* Ehrliche Erwartung statt erfundener Schätzung: es gibt keine
                belastbaren Dauer-/Kostenprognosen; der Fortschritt ist während
                der Analyse je Phase sichtbar. */}
            <p className="text-xs text-muted-foreground">
              Die Dauer hängt vom Umfang der Unterlagen ab — der Fortschritt ist
              während der Analyse Schritt für Schritt sichtbar. Die Kosten sind
              durch das Limit oben begrenzt.
            </p>

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
        )}

        {!hasActiveRun && (
          <DialogFooter className="shrink-0">
            <Button variant="outline" onClick={handleCancel}>
              Abbrechen
            </Button>
            <Button onClick={handleStart} disabled={cloudConfirmationMissing}>
              Analyse starten
            </Button>
          </DialogFooter>
        )}
      </DialogContent>
    </Dialog>
  )
}

function ActiveRunBody({ onClose }: { onClose: () => void }) {
  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-muted-foreground">
        Eine Analyse läuft bereits. Pro Antrag ist ein Durchlauf gleichzeitig
        möglich.
      </p>
      <DialogFooter>
        <Button onClick={onClose}>Schließen</Button>
      </DialogFooter>
    </div>
  )
}

function CompactBody({ available }: { available: boolean }) {
  return (
    <div className="flex flex-col gap-4">
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
