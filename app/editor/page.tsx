"use client"

import * as React from "react"
import { AppShell } from "@/components/shell/app-shell"
import { ProposalEditor } from "@/components/editor/proposal-editor"
import { currentUser, projects, activeProjectId } from "@/lib/mock-data"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectGroup,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import type { CostStatus } from "@/components/editor/cost-status-bar"

type SuggestionState = "list" | "loading" | "failed" | "off"

const editorStepStatus = [
  "done",
  "done",
  "done",
  "done",
  "current",
  "todo",
  "todo",
  "todo",
] as const

export default function EditorPage() {
  const [costStatus, setCostStatus] = React.useState<CostStatus>("ok")
  const [suggestionState, setSuggestionState] =
    React.useState<SuggestionState>("list")

  return (
    <AppShell
      user={currentUser}
      projects={projects}
      activeProjectId={activeProjectId}
      currentStep={5}
      stepStatus={[...editorStepStatus]}
    >
      <div className="border-b border-border bg-muted/30 px-6 py-2">
        <div className="flex flex-wrap items-center gap-4">
          <span className="text-xs font-medium text-muted-foreground">
            Demo-Zustände:
          </span>
          <label className="flex items-center gap-2 text-xs text-muted-foreground">
            Kostenleiste
            <Select
              value={costStatus}
              onValueChange={(v) => setCostStatus(v as CostStatus)}
            >
              <SelectTrigger size="sm" className="h-7 w-40">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem value="ok">Normal</SelectItem>
                  <SelectItem value="warn">Warnung (80%)</SelectItem>
                  <SelectItem value="stopped">Gestoppt (100%)</SelectItem>
                </SelectGroup>
              </SelectContent>
            </Select>
          </label>
          <label className="flex items-center gap-2 text-xs text-muted-foreground">
            KI-Vorschläge
            <Select
              value={suggestionState}
              onValueChange={(v) => setSuggestionState(v as SuggestionState)}
            >
              <SelectTrigger size="sm" className="h-7 w-40">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem value="list">Liste</SelectItem>
                  <SelectItem value="loading">Lädt</SelectItem>
                  <SelectItem value="failed">Fehlgeschlagen</SelectItem>
                  <SelectItem value="off">Deaktiviert</SelectItem>
                </SelectGroup>
              </SelectContent>
            </Select>
          </label>
        </div>
      </div>
      <ProposalEditor costStatus={costStatus} suggestionState={suggestionState} />
    </AppShell>
  )
}
