"use client"

// 6-Schritte-Stepper: Schritte und Labels aus dem einen Katalog
// (lib/workflow.ts), Schrittstatus aus Backend-Artefakten via
// WorkflowRunProvider. Der aktuelle Schritt kommt aus der Route — ein
// besuchter Screen ist dadurch nie automatisch «erledigt». Farbe trägt nie
// allein die Information: jeder Schritt zeigt den Statustext.

import * as React from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { Check } from "lucide-react"
import { useActiveRun } from "@/components/providers/workflow-run-provider"
import { cn } from "@/lib/utils"
import {
  STEP_STATUS_LABELS,
  stepForPathname,
  WORKFLOW_STEPS,
  type StepUiStatus,
} from "@/lib/workflow"

interface WorkflowStepperProps {
  variant?: "full" | "mini"
  className?: string
}

const STATUS_TEXT_CLASS: Record<StepUiStatus, string> = {
  abgeschlossen: "text-status-fulfilled",
  bereit_zur_pruefung: "text-status-fulfilled",
  eingaben_fehlen: "text-status-partial",
  blockiert: "text-status-blocker",
  fehlgeschlagen: "text-status-blocker",
  in_bearbeitung: "text-foreground",
  nicht_begonnen: "text-muted-foreground",
}

const DOT_CLASS: Record<StepUiStatus, string> = {
  abgeschlossen: "bg-status-fulfilled",
  bereit_zur_pruefung: "bg-status-fulfilled",
  eingaben_fehlen: "bg-status-partial",
  blockiert: "bg-status-blocker",
  fehlgeschlagen: "bg-status-blocker",
  in_bearbeitung: "bg-primary",
  nicht_begonnen: "bg-border",
}

export function WorkflowStepper({
  variant = "full",
  className,
}: WorkflowStepperProps) {
  const pathname = usePathname()
  const { statuses } = useActiveRun()
  const currentStep = stepForPathname(pathname)

  // Mini variant: a compact row of dots + current step summary
  if (variant === "mini") {
    return (
      <div
        className={cn(
          "flex h-10 items-center gap-3 border-b border-border bg-card px-4",
          className
        )}
      >
        <div className="flex items-center gap-1" aria-hidden>
          {WORKFLOW_STEPS.map((s) => (
            <span
              key={s.id}
              className={cn("size-1.5 rounded-full", DOT_CLASS[statuses[s.id]])}
            />
          ))}
        </div>
        <span className="text-xs text-muted-foreground">
          {currentStep ? (
            <>
              <span className="font-medium text-foreground">
                {`Schritt ${currentStep.step} von ${WORKFLOW_STEPS.length}`}
              </span>
              {` — ${currentStep.label}`}
            </>
          ) : (
            `${WORKFLOW_STEPS.length} Arbeitsschritte`
          )}
        </span>
      </div>
    )
  }

  // Full variant: compact horizontal step strip that fits 1280 px without
  // scrolling. Each step shows number badge + label + status text.
  return (
    <nav
      aria-label="Arbeitsschritte"
      className={cn(
        "flex w-full items-stretch border-b border-border bg-card",
        className
      )}
    >
      <ol className="flex w-full items-stretch">
        {WORKFLOW_STEPS.map((s, i) => {
          const status = statuses[s.id]
          const statusLabel = STEP_STATUS_LABELS[status]
          const isCurrent = currentStep?.id === s.id
          const isLast = i === WORKFLOW_STEPS.length - 1
          return (
            <li key={s.id} className="flex min-w-0 flex-1 items-stretch">
              <Link
                href={s.href}
                aria-current={isCurrent ? "step" : undefined}
                title={`${s.subLabel} — ${statusLabel}`}
                aria-label={`Schritt ${s.step}: ${s.label} — ${statusLabel}`}
                className={cn(
                  "flex min-h-[44px] w-full min-w-0 items-center gap-2 px-2 py-1.5 outline-none transition-colors hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring",
                  isCurrent && "bg-accent/60"
                )}
              >
                <span
                  className={cn(
                    "flex size-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold",
                    status === "abgeschlossen" &&
                      "bg-status-fulfilled/15 text-status-fulfilled",
                    (status === "blockiert" || status === "fehlgeschlagen") &&
                      "bg-status-blocker/15 text-status-blocker",
                    status === "eingaben_fehlen" &&
                      "bg-status-partial/15 text-status-partial",
                    status !== "abgeschlossen" &&
                      status !== "blockiert" &&
                      status !== "fehlgeschlagen" &&
                      status !== "eingaben_fehlen" &&
                      (isCurrent
                        ? "bg-primary text-primary-foreground"
                        : "border border-border bg-muted text-muted-foreground")
                  )}
                >
                  {status === "abgeschlossen" ? (
                    <Check className="size-3.5" />
                  ) : (
                    s.step
                  )}
                </span>
                <span className="flex min-w-0 flex-col">
                  <span
                    className={cn(
                      "truncate text-xs font-medium leading-tight",
                      status === "nicht_begonnen" && !isCurrent
                        ? "text-muted-foreground"
                        : "text-foreground"
                    )}
                  >
                    {s.label}
                  </span>
                  <span
                    className={cn(
                      "truncate text-[10px] leading-tight",
                      STATUS_TEXT_CLASS[status]
                    )}
                  >
                    {statusLabel}
                  </span>
                </span>
              </Link>
              {!isLast && (
                <div aria-hidden className="flex shrink-0 items-center">
                  <span className="h-px w-3 bg-border" />
                </div>
              )}
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
