"use client"

import * as React from "react"
import {
  Activity,
  ArrowRight,
  BrainCircuit,
  Braces,
  Cpu,
  Database,
  Eye,
  ListChecks,
  ShieldAlert,
  UserRoundCheck,
  type LucideIcon,
} from "lucide-react"
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion"
import { Button } from "@/components/ui/button"
import {
  Sheet,
  SheetClose,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { WORKFLOW_STEPS } from "@/lib/workflow"
import { cn } from "@/lib/utils"
import {
  MODEL_ROUTE_NOTICE,
  type KiTeamRole,
} from "@/lib/ki-team-data"
import { AvailabilityBadge, ModeBadge } from "./mode-badge"
import { RoleIcon } from "./role-card"

interface RoleDrawerProps {
  role: KiTeamRole | null
  open: boolean
  onOpenChange: (open: boolean) => void
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
    <section className={className}>
      <h3 className="flex items-center gap-1.5 text-xs font-semibold tracking-wide text-muted-foreground uppercase">
        {Icon && (
          <Icon aria-hidden="true" className={cn("size-3.5", iconClassName)} />
        )}
        {label}
      </h3>
      <div className="mt-1.5 text-sm leading-relaxed text-foreground">
        {children}
      </div>
    </section>
  )
}

function activeStepLabels(role: KiTeamRole): string[] {
  return role.activeSteps.map((stepNumber) => {
    const step = WORKFLOW_STEPS.find((item) => item.step === stepNumber)
    if (!step) {
      throw new Error(`Unbekannter Workflow-Schritt: ${stepNumber}`)
    }
    return step.label
  })
}

function ModelRouteDetails({ role }: Readonly<{ role: KiTeamRole }>) {
  if (role.modelInfo.kind === "none") {
    return <p>{role.modelInfo.description}</p>
  }

  return (
    <div className="flex flex-col gap-3">
      <dl className="grid gap-2">
        <div className="flex items-start justify-between gap-4 rounded-md bg-muted/55 px-3 py-2.5">
          <dt className="text-xs font-medium text-muted-foreground">
            Primär vorgesehen
          </dt>
          <dd className="text-right">
            <span className="block font-medium">{role.modelInfo.primary.model}</span>
            <span className="block text-xs text-muted-foreground">
              {role.modelInfo.primary.provider}
            </span>
          </dd>
        </div>
        {role.modelInfo.fallback && (
          <div className="flex items-start justify-between gap-4 rounded-md border border-border/70 px-3 py-2.5">
            <dt className="text-xs font-medium text-muted-foreground">
              Ersatzroute
            </dt>
            <dd className="text-right">
              <span className="block font-medium">
                {role.modelInfo.fallback.model}
              </span>
              <span className="block text-xs text-muted-foreground">
                {role.modelInfo.fallback.provider}
              </span>
            </dd>
          </div>
        )}
      </dl>
      {role.modelInfo.scope && (
        <p className="text-xs leading-relaxed text-muted-foreground">
          {role.modelInfo.scope}
        </p>
      )}
      <p className="rounded-md border border-border/70 bg-muted/30 p-3 text-xs leading-relaxed text-muted-foreground">
        {MODEL_ROUTE_NOTICE}
      </p>
    </div>
  )
}

export function RoleDrawer({
  role,
  open,
  onOpenChange,
  finalFocusRef,
}: Readonly<RoleDrawerProps>) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        finalFocus={finalFocusRef}
        className="flex gap-0 overflow-hidden p-0 data-[side=right]:w-full data-[side=right]:sm:w-[560px] data-[side=right]:sm:max-w-[calc(100vw-3rem)]"
      >
        {role && (
          <>
            <SheetHeader className="border-b border-border bg-muted/40 p-5 pr-14 sm:p-6 sm:pr-16">
              <div className="flex items-start gap-3">
                <RoleIcon role={role} className="size-11" />
                <div className="min-w-0 flex-1">
                  <SheetTitle className="text-lg leading-snug">
                    {role.name}
                  </SheetTitle>
                  <p className="mt-1.5 max-w-[56ch] text-sm leading-relaxed text-muted-foreground">
                    {role.specialization}
                  </p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <ModeBadge mode={role.mode} />
                    <AvailabilityBadge role={role} />
                  </div>
                </div>
              </div>
              <SheetDescription className="sr-only">
                Aufgabe, Ergebnis, menschliche Entscheidung und technische Zuordnung der
                Funktion {role.name}.
              </SheetDescription>
            </SheetHeader>

            <div className="min-h-0 flex-1 overflow-y-auto">
              <div className="flex flex-col gap-5 p-5 sm:p-6">
                <Field label="Aufgabe" icon={ListChecks}>
                  {role.task}
                </Field>

                <div className="grid gap-3">
                  <div className="rounded-lg border border-border bg-card p-4">
                    <Field label="Ergebnis" icon={ArrowRight}>
                      {role.outputSummary}
                    </Field>
                  </div>
                  <div className="rounded-lg border border-status-partial/35 bg-status-partial/5 p-4">
                    <Field
                      label="Ihre Entscheidung"
                      icon={UserRoundCheck}
                      iconClassName="text-status-partial"
                    >
                      {role.humanReview}
                    </Field>
                  </div>
                </div>

                <div className="rounded-lg border border-border bg-muted/35 p-4">
                  <Field label="Entscheidungsgrenze" icon={ShieldAlert}>
                    {role.decisionBoundary}
                  </Field>
                </div>

                <div className="flex flex-wrap items-center gap-3 border-y border-border py-3">
                  <h3 className="flex items-center gap-1.5 text-xs font-semibold tracking-wide text-muted-foreground uppercase">
                    <Activity aria-hidden="true" className="size-3.5" />
                    Aktiv in
                  </h3>
                  <ul className="flex flex-wrap gap-1.5">
                    {activeStepLabels(role).map((label) => (
                      <li
                        key={label}
                        className="rounded-full bg-muted px-2.5 py-1 text-xs font-medium text-foreground"
                      >
                        {label}
                      </li>
                    ))}
                  </ul>
                </div>

                <Accordion className="overflow-hidden rounded-lg border border-border px-4">
                  <AccordionItem value="data-framework">
                    <AccordionTrigger className="py-4 hover:no-underline">
                      Daten &amp; Rahmen
                    </AccordionTrigger>
                    <AccordionContent className="pb-4">
                      <div className="grid gap-5 pt-1 sm:grid-cols-2">
                        <Field label="Arbeitsgrundlage" icon={Database}>
                          {role.worksWith}
                        </Field>
                        <Field label="Datenzugriff" icon={Eye}>
                          {role.dataAccess}
                        </Field>
                      </div>
                    </AccordionContent>
                  </AccordionItem>
                  <AccordionItem value="technical-details">
                    <AccordionTrigger className="py-4 hover:no-underline">
                      Technische Details
                    </AccordionTrigger>
                    <AccordionContent className="pb-4">
                      <div className="flex flex-col gap-5 pt-1">
                        <Field label="KI-Modell" icon={BrainCircuit}>
                          <ModelRouteDetails role={role} />
                        </Field>
                        <Field label="Ausführungslogik" icon={Cpu}>
                          {role.providerSummary}
                        </Field>
                        <Field label="Technische Komponenten" icon={Braces}>
                          <ul className="flex flex-col gap-1.5">
                            {role.technicalComponents.map((component) => (
                              <li key={component}>
                                <code className="rounded bg-muted px-1.5 py-0.5 text-xs">
                                  {component}
                                </code>
                              </li>
                            ))}
                          </ul>
                        </Field>
                        <Field label="Interne Quelle">
                          <code className="break-words rounded bg-muted px-1.5 py-0.5 text-xs">
                            {role.technicalSource}
                          </code>
                        </Field>
                        <Field label="Datenklassen-Regel">
                          {role.dataClassRule}
                        </Field>
                      </div>
                    </AccordionContent>
                  </AccordionItem>
                </Accordion>
              </div>
            </div>

            <SheetFooter className="flex-row justify-end border-t border-border bg-muted/30 px-5 py-3 sm:px-6">
              <SheetClose render={<Button variant="outline" />}>
                Schliessen
              </SheetClose>
            </SheetFooter>
          </>
        )}
      </SheetContent>
    </Sheet>
  )
}
