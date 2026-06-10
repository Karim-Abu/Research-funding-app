"use client"

import * as React from "react"
import { ChevronDown, ChevronRight } from "lucide-react"
import { AppShell } from "@/components/shell/app-shell"
import { ReviewScreen } from "@/components/review/review-screen"
import { currentUser, projects, activeProjectId } from "@/lib/mock-data"
import { PAGE_SCENARIOS, type PageScenario } from "@/lib/review-mock-data"
import { cn } from "@/lib/utils"
import type { StepStatus } from "@/lib/types"

const stepStatus: StepStatus[] = [
  "done",
  "done",
  "done",
  "done",
  "done",
  "current",
  "upcoming",
  "upcoming",
]

// Set to true only during internal prototyping — never in the evaluation view.
const showDebugControls = false

export default function ReviewPage() {
  const [scenario, setScenario] = React.useState<PageScenario>("default")
  const [showDebug, setShowDebug] = React.useState(false)

  return (
    <AppShell
      user={currentUser}
      projects={projects}
      activeProjectId={activeProjectId}
      currentStep={6}
      stepStatus={stepStatus}
    >
      <ReviewScreen scenario={scenario} />

      {/* Debug scenario switcher — hidden from normal user-facing UI */}
      {showDebugControls && (
      <div className="border-t border-border px-6 py-4">
        <button
          type="button"
          onClick={() => setShowDebug((v) => !v)}
          className={cn(
            "flex items-center gap-1.5 rounded text-xs font-medium text-muted-foreground",
            "outline-none transition-colors hover:text-foreground",
            "focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          )}
          aria-expanded={showDebug}
        >
          {showDebug ? (
            <ChevronDown className="size-3.5" />
          ) : (
            <ChevronRight className="size-3.5" />
          )}
          Demo: Seitenzustände testen
        </button>

        {showDebug && (
          <div className="mt-3 flex flex-wrap gap-2">
            {PAGE_SCENARIOS.map((s) => (
              <button
                key={s.id}
                type="button"
                onClick={() => setScenario(s.id)}
                className={cn(
                  "inline-flex h-8 items-center rounded-full border px-3 text-xs font-medium transition-colors",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
                  scenario === s.id
                    ? "border-foreground bg-foreground text-background"
                    : "border-border bg-card text-foreground hover:bg-accent hover:text-accent-foreground"
                )}
              >
                {s.label}
              </button>
            ))}
          </div>
        )}
      </div>
      )}
    </AppShell>
  )
}
