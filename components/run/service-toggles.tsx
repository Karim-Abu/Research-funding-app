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
            {available ? availableLabel : "Dienst aktuell nicht verfügbar"}
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

export function LLMToggle(props: Omit<ServiceToggleProps, "title" | "subtitle">) {
  return (
    <ServiceToggle
      {...props}
      title="KI-Unterstützung"
      subtitle="Erstellt Textvorschläge und Analysen"
      availableLabel="KI-Unterstützung verfügbar"
    />
  )
}

export function WebSearchToggle(
  props: Omit<ServiceToggleProps, "title" | "subtitle">
) {
  return (
    <ServiceToggle
      {...props}
      title="Webrecherche"
      subtitle="Sucht öffentliche Informationen, z. B. zu Markt und Partnern"
      availableLabel="Webrecherche verfügbar"
    />
  )
}
