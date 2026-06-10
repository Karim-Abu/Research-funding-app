"use client"

import { AppShell } from "@/components/shell/app-shell"
import { ProposalEditor } from "@/components/editor/proposal-editor"
import { currentUser, projects, activeProjectId } from "@/lib/mock-data"

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
  return (
    <AppShell
      user={currentUser}
      projects={projects}
      activeProjectId={activeProjectId}
      currentStep={5}
      stepStatus={[...editorStepStatus]}
    >
      <ProposalEditor />
    </AppShell>
  )
}
