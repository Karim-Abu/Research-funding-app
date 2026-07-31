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
              : "Nicht verfügbar"}
          </span>
        </span>
        {!available && unavailableReason && (
          <p className="text-xs text-muted-foreground">{unavailableReason}</p>
        )}
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
      title={isDemo ? "Demo-Vorschläge" : "Live-KI-Unterstützung"}
      subtitle={
        isDemo
          ? "Erstellt gekennzeichnete Testvorschläge ohne echtes KI-Modell"
          : "Erstellt modellgenerierte Textvorschläge und Analysen"
      }
      availableLabel={
        isDemo
          ? "Demo"
          : "Live-KI verfügbar"
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
      // Die Verfügbarkeitsbedingung steht bereits im unavailableReason, die
      // Query-Freigabe in der Suchanfragen-Liste darunter. Hier nur der Zweck.
      subtitle="Sucht öffentliche Informationen, z. B. zu Markt und Umfeld."
      availableLabel="Webrecherche verfügbar"
    />
  )
}
