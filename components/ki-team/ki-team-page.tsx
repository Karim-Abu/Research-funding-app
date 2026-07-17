"use client"

import * as React from "react"
import { FlaskConical } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs"
import { getKiTeamPhases, kiTeamTexts } from "@/lib/ki-team-data"
import type { KiTeamRole } from "@/lib/ki-team-data"
import { HumanApprovalsView } from "./static-sections"
import { PhaseBand } from "./phase-band"
import { ResponsibilitySummary } from "./responsibility-summary"
import { RoleCatalog } from "./role-catalog"
import { RoleDrawer } from "./role-drawer"

const phases = getKiTeamPhases()

export function KiTeamScreen() {
  const [openRole, setOpenRole] = React.useState<KiTeamRole | null>(null)
  const [openInstanceId, setOpenInstanceId] = React.useState<string | null>(null)
  const [drawerOpen, setDrawerOpen] = React.useState(false)
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
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-8 pb-12 sm:gap-8 sm:px-6 lg:px-8">
      <header className="flex flex-col gap-4">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <h1 className="text-2xl leading-tight font-semibold text-foreground sm:text-[28px]">
              {kiTeamTexts.title}
            </h1>
            <p className="mt-2 max-w-[70ch] text-sm leading-relaxed text-muted-foreground sm:text-base">
              {kiTeamTexts.subtitle}
            </p>
          </div>
          <Badge
            variant="outline"
            className="min-h-7 w-fit shrink-0 gap-1.5 border-border bg-muted/55 px-3 text-muted-foreground"
          >
            <FlaskConical aria-hidden="true" />
            {kiTeamTexts.prototypeBadge}
          </Badge>
        </div>
        <p className="max-w-3xl text-sm leading-relaxed text-foreground">
          {kiTeamTexts.intro}
        </p>
      </header>

      <ResponsibilitySummary />

      <Tabs defaultValue="workflow" className="gap-5">
        <TabsList className="grid h-auto w-full grid-cols-3 p-1 sm:w-fit sm:min-w-[31rem]">
          <TabsTrigger
            value="workflow"
            className="min-h-11 px-2 py-2 text-center leading-tight whitespace-normal"
          >
            Im Ablauf
          </TabsTrigger>
          <TabsTrigger
            value="specialists"
            className="min-h-11 px-2 py-2 text-center leading-tight whitespace-normal"
          >
            Spezialisten
          </TabsTrigger>
          <TabsTrigger
            value="approvals"
            className="min-h-11 px-2 py-2 text-center leading-tight whitespace-normal"
          >
            Ihre Freigaben
          </TabsTrigger>
        </TabsList>

        <TabsContent value="workflow">
          <PhaseBand
            phases={phases}
            openInstanceId={openInstanceId}
            onOpenRole={handleOpenRole}
          />
        </TabsContent>

        <TabsContent value="specialists">
          <RoleCatalog
            openInstanceId={openInstanceId}
            onOpenRole={handleOpenRole}
          />
        </TabsContent>

        <TabsContent value="approvals">
          <HumanApprovalsView />
        </TabsContent>
      </Tabs>

      <RoleDrawer
        role={openRole}
        open={drawerOpen}
        onOpenChange={handleDrawerOpenChange}
        finalFocusRef={finalFocusRef}
      />
    </div>
  )
}
