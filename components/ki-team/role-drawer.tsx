"use client"

import * as React from "react"
import {
  ArrowRight,
  Clock,
  Cpu,
  Eye,
  History,
  ListChecks,
  TriangleAlert,
  UserRoundCheck,
  type LucideIcon,
} from "lucide-react"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion"
import { Separator } from "@/components/ui/separator"
import { cn } from "@/lib/utils"
import { kiTeamTexts, MODE_LABELS } from "@/lib/ki-team-data"
import type { KiTeamRole } from "@/lib/ki-team-data"
import { ModeBadge, StatusChip } from "./mode-badge"

interface RoleDrawerProps {
  role: KiTeamRole | null
  open: boolean
  onOpenChange: (open: boolean) => void
  detailMode: boolean
  /** Element, das nach dem Schliessen den Fokus zurückerhält (die Karte). */
  finalFocusRef: React.RefObject<HTMLElement | null>
}

interface FieldProps {
  label: string
  icon?: LucideIcon
  iconClassName?: string
  className?: string
  children: React.ReactNode
}

function Field({
  label,
  icon: Icon,
  iconClassName,
  className,
  children,
}: Readonly<FieldProps>) {
  return (
    <div className={className}>
      <p className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {Icon && (
          <Icon aria-hidden="true" className={cn("size-3.5", iconClassName)} />
        )}
        {label}
      </p>
      <div className="mt-1 text-sm leading-relaxed text-foreground">{children}</div>
    </div>
  )
}

/**
 * Detail-Drawer einer Rolle. Rein statische Rollenbeschreibung — keine
 * Live-Daten, keine API-Aufrufe, keine Rohinhalte. Felder sind in Gruppen
 * organisiert; die menschliche Prüfung ist als Vertrauens-Callout hervorgehoben.
 */
export function RoleDrawer({
  role,
  open,
  onOpenChange,
  detailMode,
  finalFocusRef,
}: Readonly<RoleDrawerProps>) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        finalFocus={finalFocusRef}
        className="flex w-full flex-col gap-0 overflow-y-auto p-0 sm:max-w-[440px]"
      >
        {role && (
          <>
            <SheetHeader className="border-b pr-12">
              <div className="flex flex-wrap items-center gap-2">
                <ModeBadge mode={role.mode} />
                <StatusChip role={role} />
              </div>
              <SheetTitle className="mt-1">{role.name}</SheetTitle>
              <SheetDescription>{role.short}</SheetDescription>
            </SheetHeader>

            <div className="flex flex-col gap-5 p-4">
              <Field label="Aufgabe" icon={ListChecks}>
                {role.aufgabe}
              </Field>

              {/* Kompakte Fakten-Gruppe. */}
              <div className="grid gap-4 rounded-lg border border-border/70 bg-muted/30 p-3 sm:grid-cols-2">
                <Field label="Wann aktiv" icon={Clock}>
                  {role.aktiv}
                </Field>
                <Field label="Modus & Provider" icon={Cpu}>
                  {MODE_LABELS[role.mode]} · {role.provider}
                </Field>
                <Field
                  label="Eingaben & Ausgaben"
                  icon={ArrowRight}
                  className="sm:col-span-2"
                >
                  <p>
                    {role.eingaben}
                    <span aria-hidden="true" className="mx-1.5 text-muted-foreground">
                      →
                    </span>
                    <span className="sr-only">wird zu</span>
                    {role.ausgaben}
                  </p>
                </Field>
              </div>

              <Field label="Daten, die diese Rolle sieht" icon={Eye}>
                {role.daten}
              </Field>

              {/* Menschliche Prüfung — hervorgehobener Vertrauens-Hinweis. */}
              <div className="rounded-lg border border-status-partial/30 bg-status-partial/5 p-3">
                <Field
                  label="Menschliche Prüfung"
                  icon={UserRoundCheck}
                  iconClassName="text-status-partial"
                >
                  {role.menschlichePruefung}
                </Field>
              </div>

              <Field label="Grenzen & Risiken" icon={TriangleAlert}>
                {role.grenzen}
              </Field>

              <Separator />

              <Field label="Letzter Lauf" icon={History}>
                {kiTeamTexts.letzterLauf}
              </Field>

              {detailMode && (
                <>
                  <Separator />
                  <Accordion>
                    <AccordionItem value="technische-details">
                      <AccordionTrigger>Technische Details</AccordionTrigger>
                      <AccordionContent>
                        <div className="flex flex-col gap-3">
                          <Field label="Werkzeuge / Regelquellen">
                            <code className="rounded bg-muted px-1.5 py-0.5 text-xs">
                              {role.technischeQuelle}
                            </code>
                          </Field>
                          <Field label="Datenklassen-Regel">
                            {role.datenklassenRegel}
                          </Field>
                        </div>
                      </AccordionContent>
                    </AccordionItem>
                  </Accordion>
                </>
              )}
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  )
}
