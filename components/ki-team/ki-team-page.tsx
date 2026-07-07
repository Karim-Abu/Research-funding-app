"use client"

import * as React from "react"
import { Workflow } from "lucide-react"
import { cn } from "@/lib/utils"
import { Card, CardContent } from "@/components/ui/card"
import { getKiTeamPhases, kiTeamTexts } from "@/lib/ki-team-data"
import type { KiTeamRole, RoleMode } from "@/lib/ki-team-data"
import { Legend } from "./legend"
import { PhaseBand } from "./phase-band"
import { RoleDrawer } from "./role-drawer"
import { StaticSections } from "./static-sections"

const phases = getKiTeamPhases()

/** Umschalter „Einfach | Details" — steuert Karten- und Drawer-Detailgrad. */
function DetailToggle({
  detailMode,
  onChange,
}: Readonly<{
  detailMode: boolean
  onChange: (detail: boolean) => void
}>) {
  const options = [
    { detail: false, label: "Einfach" },
    { detail: true, label: "Details" },
  ]
  return (
    <fieldset className="flex shrink-0 items-center gap-0.5 rounded-lg border border-border bg-muted p-0.5">
      <legend className="sr-only">Detailgrad der Anzeige</legend>
      {options.map((option) => (
        <button
          key={option.label}
          type="button"
          aria-pressed={detailMode === option.detail}
          onClick={() => onChange(option.detail)}
          className={cn(
            "rounded-md px-3 py-1 text-sm font-medium outline-none transition-colors focus-visible:ring-2 focus-visible:ring-ring",
            detailMode === option.detail
              ? "bg-card text-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground"
          )}
        >
          {option.label}
        </button>
      ))}
    </fieldset>
  )
}

export function KiTeamScreen() {
  const [detailMode, setDetailMode] = React.useState(false)
  const [highlight, setHighlight] = React.useState<RoleMode | null>(null)
  const [openRole, setOpenRole] = React.useState<KiTeamRole | null>(null)
  const [openInstanceId, setOpenInstanceId] = React.useState<string | null>(null)
  const [drawerOpen, setDrawerOpen] = React.useState(false)
  // Karte, die den Drawer geöffnet hat — erhält nach dem Schliessen den Fokus.
  const finalFocusRef = React.useRef<HTMLElement | null>(null)

  const handleOpenRole = (
    role: KiTeamRole,
    instanceId: string,
    element: HTMLButtonElement
  ) => {
    finalFocusRef.current = element
    setOpenRole(role)
    setOpenInstanceId(instanceId)
    setDrawerOpen(true)
  }

  const handleDrawerOpenChange = (open: boolean) => {
    setDrawerOpen(open)
    if (!open) setOpenInstanceId(null)
  }

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-6 px-6 py-8 pb-12">
      {/* Kopfbereich */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-foreground">
            {kiTeamTexts.titel}
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {kiTeamTexts.untertitel}
          </p>
        </div>
        <DetailToggle detailMode={detailMode} onChange={setDetailMode} />
      </div>

      {/* Intro-Karte mit Legende */}
      <Card size="sm">
        <CardContent className="flex flex-col gap-4">
          <p className="max-w-prose text-sm leading-relaxed text-foreground">
            {kiTeamTexts.intro}
          </p>
          <div className="flex flex-col gap-2 border-t border-border/60 pt-4">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Legende
            </p>
            <Legend highlight={highlight} onHighlight={setHighlight} />
          </div>
        </CardContent>
      </Card>

      {/* Ablaufsteuerungs-Hinweis — bewusst keine Rolle als „Chef-Agent". */}
      <div
        role="note"
        className="flex items-start gap-2.5 rounded-lg border border-border bg-muted/40 px-3.5 py-2.5"
      >
        <Workflow
          aria-hidden="true"
          className="mt-0.5 size-4 shrink-0 text-muted-foreground"
        />
        <p className="text-sm text-foreground">
          {kiTeamTexts.ablaufsteuerungHinweis}
        </p>
      </div>

      {/* Phasenband */}
      <PhaseBand
        phases={phases}
        detailMode={detailMode}
        highlight={highlight}
        openInstanceId={openInstanceId}
        onOpenRole={handleOpenRole}
      />

      {/* Statische Erklärsektionen */}
      <StaticSections />

      <RoleDrawer
        role={openRole}
        open={drawerOpen}
        onOpenChange={handleDrawerOpenChange}
        detailMode={detailMode}
        finalFocusRef={finalFocusRef}
      />
    </div>
  )
}
