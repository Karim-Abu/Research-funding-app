"use client"

import { Switch } from "@/components/ui/switch"
import { cn } from "@/lib/utils"

interface ServiceToggleProps {
  id: string
  title: string
  subtitle: string
  checked: boolean
  onCheckedChange: (checked: boolean) => void
  /** Service availability — false shows gray dot + disables. */
  available: boolean
  availableLabel?: string
  disabled?: boolean
  /** Konkreter Grund, warum der Dienst nicht verfügbar ist (A4) — ersetzt
   *  das generische «Dienst aktuell nicht verfügbar». */
  unavailableReason?: string
}

/** Shared toggle row used for "KI-Unterstützung" and "Webrecherche". */
function ServiceToggle({
  id,
  title,
  subtitle,
  checked,
  onCheckedChange,
  available,
  availableLabel = "Dienst verfügbar",
  disabled,
  unavailableReason,
}: ServiceToggleProps) {
  const isDisabled = disabled || !available
  return (
    <div className="flex items-start justify-between gap-4">
      <div className="flex flex-col gap-1">
        <label htmlFor={id} className="text-sm font-medium text-foreground">
          {title}
        </label>
        <p className="text-xs text-muted-foreground">{subtitle}</p>
        <span className="flex items-center gap-1.5 text-xs">
          <span
            className={cn(
              "size-2 rounded-full",
              available ? "bg-status-fulfilled" : "bg-muted-foreground/40"
            )}
          />
          <span className="text-muted-foreground">
            {available
              ? availableLabel
              : (unavailableReason ?? "Dienst aktuell nicht verfügbar")}
          </span>
        </span>
      </div>
      <Switch
        id={id}
        checked={checked && available}
        onCheckedChange={onCheckedChange}
        disabled={isDisabled}
      />
    </div>
  )
}

export function LLMToggle({
  generationMode = "unavailable",
  ...props
}: Omit<ServiceToggleProps, "title" | "subtitle"> & {
  generationMode?: "unavailable" | "fake_demo" | "real_eval" | "live_unavailable"
}) {
  const isDemo = generationMode === "fake_demo"
  return (
    <ServiceToggle
      {...props}
      title={isDemo ? "Demo-Vorschläge" : "KI-Unterstützung"}
      subtitle={
        isDemo
          ? "Erstellt gekennzeichnete Testvorschläge ohne echtes KI-Modell"
          : "Erstellt modellgenerierte Textvorschläge und Analysen"
      }
      availableLabel={
        isDemo
          ? "Demo-Generator verfügbar – kein Modellaufruf"
          : "KI-Unterstützung für Evaluationsfälle verfügbar"
      }
    />
  )
}

export function WebSearchToggle(
  props: Omit<ServiceToggleProps, "title" | "subtitle">
) {
  return (
    <ServiceToggle
      {...props}
      title="Öffentliche Webrecherche"
      subtitle="Sucht öffentliche Informationen, z. B. zu Markt und Umfeld — nur bei öffentlicher Vertraulichkeitsstufe verfügbar. Jede Suchanfrage passiert die Query-Prüfung."
      availableLabel="Webrecherche verfügbar"
    />
  )
}
