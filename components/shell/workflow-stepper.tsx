"use client"

import * as React from "react"
import Link from "next/link"
import { Check } from "lucide-react"
import { cn } from "@/lib/utils"
import type { StepStatus } from "@/lib/types"
import { workflowSteps } from "@/lib/mock-data"

interface WorkflowStepperProps {
  currentStep: number
  /** Status for each workflow step, in order. */
  stepStatus: StepStatus[]
  variant?: "full" | "mini"
  className?: string
}

export function WorkflowStepper({
  currentStep,
  stepStatus,
  variant = "full",
  className,
}: WorkflowStepperProps) {
  // Mini variant: a compact row of dots + current step summary
  if (variant === "mini") {
    const current = workflowSteps.find((s) => s.step === currentStep)
    return (
      <div
        className={cn(
          "flex h-10 items-center gap-3 border-b border-border bg-card px-4",
          className
        )}
      >
        <div className="flex items-center gap-1" aria-hidden>
          {workflowSteps.map((s) => {
            const status = stepStatus[s.step - 1] ?? "upcoming"
            return (
              <span
                key={s.step}
                className={cn(
                  "size-1.5 rounded-full",
                  status === "done" && "bg-primary",
                  status === "current" && "bg-primary",
                  status === "upcoming" && "bg-border"
                )}
              />
            )
          })}
        </div>
        <span className="text-xs text-muted-foreground">
          <span className="font-medium text-foreground">
            {`Schritt ${currentStep} von ${workflowSteps.length}`}
          </span>
          {current && ` — ${current.label}: ${current.subLabel}`}
        </span>
      </div>
    )
  }

  // Full variant: compact horizontal step strip that fits 1280 px without scrolling.
  // Each step shows number-badge + short label only; sub-label is in a tooltip.
  return (
    <nav
      aria-label="Arbeitsschritte"
      className={cn(
        "flex w-full items-stretch border-b border-border bg-card",
        className
      )}
    >
      <ol className="flex w-full items-stretch">
        {workflowSteps.map((s, i) => {
          const status = stepStatus[s.step - 1] ?? "upcoming"
          const isLast = i === workflowSteps.length - 1
          return (
            <li key={s.step} className="flex min-w-0 flex-1 items-stretch">
              <Link
                href={s.href}
                aria-current={status === "current" ? "step" : undefined}
                title={s.subLabel}
                className={cn(
                  "flex min-h-[44px] w-full min-w-0 items-center gap-2 px-2 py-2 outline-none transition-colors hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring",
                  status === "current" && "bg-accent/60"
                )}
              >
                <span
                  className={cn(
                    "flex size-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold",
                    status === "done" && "bg-primary/15 text-primary",
                    status === "current" && "bg-primary text-primary-foreground",
                    status === "upcoming" &&
                      "border border-border bg-muted text-muted-foreground"
                  )}
                >
                  {status === "done" ? <Check className="size-3.5" /> : s.step}
                </span>
                <span
                  className={cn(
                    "truncate text-xs font-medium leading-tight",
                    status === "upcoming"
                      ? "text-muted-foreground"
                      : "text-foreground"
                  )}
                >
                  {s.shortLabel ?? s.label}
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
