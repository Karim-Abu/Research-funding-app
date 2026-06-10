"use client"

import * as React from "react"
import Link from "next/link"
import { Check } from "lucide-react"
import { cn } from "@/lib/utils"
import type { StepStatus } from "@/lib/types"
import { workflowSteps } from "@/lib/mock-data"

interface WorkflowStepperProps {
  currentStep: number
  /** Status for each of the 8 steps, in order. */
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
  if (variant === "mini") {
    const current = workflowSteps.find((s) => s.step === currentStep)
    return (
      <div className={cn("flex items-center gap-2", className)}>
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
        <span className="text-xs font-medium text-muted-foreground">
          {`Schritt ${currentStep} von 8: ${current?.label ?? ""}`}
        </span>
      </div>
    )
  }

  return (
    <nav
      aria-label="Arbeitsschritte"
      className={cn(
        "flex w-full items-stretch overflow-x-auto border-b border-border bg-card px-4",
        className
      )}
    >
      <ol className="flex min-w-max items-stretch">
        {workflowSteps.map((s, i) => {
          const status = stepStatus[s.step - 1] ?? "upcoming"
          const isLast = i === workflowSteps.length - 1
          return (
            <li key={s.step} className="flex items-stretch">
              <Link
                href={s.href}
                aria-current={status === "current" ? "step" : undefined}
                className="flex min-h-[44px] items-center gap-3 rounded-md px-3 py-2.5 outline-none transition-colors hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring"
              >
                <span
                  className={cn(
                    "flex size-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold",
                    status === "done" &&
                      "bg-primary/15 text-primary",
                    status === "current" &&
                      "bg-primary text-primary-foreground",
                    status === "upcoming" &&
                      "border border-border bg-muted text-muted-foreground"
                  )}
                >
                  {status === "done" ? (
                    <Check className="size-4" />
                  ) : (
                    s.step
                  )}
                </span>
                <span className="flex flex-col leading-tight">
                  <span
                    className={cn(
                      "text-sm font-medium",
                      status === "upcoming"
                        ? "text-muted-foreground"
                        : "text-foreground"
                    )}
                  >
                    {s.label}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    {s.subLabel}
                  </span>
                </span>
              </Link>
              {!isLast && (
                <div
                  aria-hidden
                  className="mx-1 flex items-center"
                >
                  <span className="h-px w-4 bg-border" />
                </div>
              )}
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
