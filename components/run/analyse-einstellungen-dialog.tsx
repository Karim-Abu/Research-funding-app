"use client"

import * as React from "react"
import { Lock } from "lucide-react"
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
import { LLMToggle, WebSearchToggle } from "./service-toggles"
import { UsageEstimateBanner } from "./usage-estimate-banner"
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
  estimateState?: "ready" | "loading" | "unavailable"
  onStart?: (settings: AnalyseSettings) => void
  onCancel?: () => void
}

const dataClassLabel: Record<DataClass, string> = {
  public: "Öffentlich",
  internal: "Intern",
  confidential: "Vertraulich",
}

export function AnalyseEinstellungenDialog({
  open,
  onOpenChange,
  role,
  dataClass,
  variant = "full",
  serviceAvailability = { ki: true, web: true },
  hasActiveRun = false,
  estimateState = "ready",
  onStart,
  onCancel,
}: AnalyseEinstellungenDialogProps) {
  // Beta-Policy: public can use validated external services; internal needs
  // explicit release in a later flow; confidential stays local-only.
  const isLocalOnlyClass = !isCloudAllowed(dataClass)

  const [ki, setKi] = React.useState(!isLocalOnlyClass)
  const [web, setWeb] = React.useState(false) // DEFAULT OFF always
  const [localSourcesOnly, setLocalSourcesOnly] = React.useState(false)
  const [costLimit, setCostLimit] = React.useState("2.00")

  const webDisabled = localSourcesOnly || !isWebAllowed(dataClass)
  const effectiveWeb = web && !webDisabled

  function handleStart() {
    onStart?.({
      ki: ki && !isLocalOnlyClass,
      web: effectiveWeb,
      localSourcesOnly,
      costLimit: Number.parseFloat(costLimit) || 0,
      // Beta: Modell-Routing ist eine Backend-/Config-Entscheidung —
      // die Drafter/Critic-Trennung bleibt cross-provider.
      model: "auto",
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
          <DialogTitle>Analyse-Einstellungen</DialogTitle>
          <DialogDescription>
            Konfigurieren Sie diesen Durchlauf, bevor Sie ihn starten.
          </DialogDescription>
        </DialogHeader>

        {hasActiveRun ? (
          <ActiveRunBody onClose={handleCancel} />
        ) : variant === "compact" ? (
          <CompactBody
            available={serviceAvailability.ki}
            estimateState={estimateState}
            onSwitchFull={() => {
              /* In a real app this would switch variant; demo only. */
            }}
          />
        ) : (
          <div className="flex flex-col gap-5 overflow-y-auto py-1 pr-1">
            {/* Local-only class banner */}
            {isLocalOnlyClass && (
              <div className="flex items-start gap-2 rounded-md border border-border bg-muted/50 p-3 text-sm text-muted-foreground">
                <Lock className="mt-0.5 size-4 shrink-0" />
                {dataClass === "internal"
                  ? "Für interne Daten benötigen externe Dienste eine Freigabe. Aktuell werden keine externen Dienste verwendet."
                  : "Für diese Datenklasse werden keine externen KI- oder Webdienste verwendet."}
              </div>
            )}

            <LLMToggle
              id="ki-toggle"
              checked={ki}
              onCheckedChange={setKi}
              available={serviceAvailability.ki && !isLocalOnlyClass}
            />
            <WebSearchToggle
              id="web-toggle"
              checked={effectiveWeb}
              onCheckedChange={setWeb}
              available={serviceAvailability.web && isWebAllowed(dataClass)}
              disabled={webDisabled}
            />

            <label className="flex items-start gap-2">
              <Checkbox
                checked={localSourcesOnly}
                onCheckedChange={(c) => {
                  const v = c === true
                  setLocalSourcesOnly(v)
                  if (v) setWeb(false)
                }}
                disabled={isLocalOnlyClass}
                className="mt-0.5"
              />
              <span className="flex flex-col gap-0.5">
                <span className="text-sm font-medium text-foreground">
                  Nur vorbereitete / hochgeladene Quellen verwenden
                </span>
                <span className="text-xs text-muted-foreground">
                  Es werden ausschließlich Ihre hochgeladenen Unterlagen
                  verwendet.
                </span>
              </span>
            </label>

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

            <UsageEstimateBanner state={estimateState} />

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
                        Modellwahl: automatisch durch System
                      </p>
                      <NumberField
                        label="Max. Textumfang"
                        helper="begrenzt die Länge der KI-Antworten"
                        defaultValue="1500"
                      />
                      <NumberField
                        label="Max. Quellen"
                        defaultValue="20"
                      />
                      <NumberField
                        label="Max. Webseiten"
                        helper="Nur freigegebene Webseiten werden durchsucht."
                        defaultValue="10"
                        disabled={!effectiveWeb}
                      />
                      <p className="text-xs text-muted-foreground">
                        Vorgaben des Admins: max. CHF 5 pro Durchlauf (Dummy)
                      </p>
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
            <Button onClick={handleStart}>Analyse starten</Button>
          </DialogFooter>
        )}
      </DialogContent>
    </Dialog>
  )
}

function NumberField({
  label,
  helper,
  defaultValue,
  disabled,
}: {
  label: string
  helper?: string
  defaultValue?: string
  disabled?: boolean
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <label className="text-sm font-medium text-foreground">{label}</label>
      <Input
        type="number"
        defaultValue={defaultValue}
        disabled={disabled}
        className="w-32"
      />
      {helper && <p className="text-xs text-muted-foreground">{helper}</p>}
    </div>
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

function CompactBody({
  available,
  estimateState,
  onSwitchFull,
}: {
  available: boolean
  estimateState: "ready" | "loading" | "unavailable"
  onSwitchFull: () => void
}) {
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
      <div className="rounded-md border border-border bg-muted/40 p-3">
        <span className="text-sm font-medium text-foreground">
          ~CHF 0.45 von CHF 2.00 (Dummy)
        </span>
        <p className="text-xs text-muted-foreground">Verbleibendes Budget</p>
      </div>
      <UsageEstimateBanner state={estimateState} />
      <button
        type="button"
        onClick={onSwitchFull}
        className="self-start text-sm font-medium text-primary underline-offset-2 hover:underline"
      >
        Einstellungen ändern
      </button>
    </div>
  )
}
