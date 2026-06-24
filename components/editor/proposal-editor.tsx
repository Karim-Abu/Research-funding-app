"use client"

import * as React from "react"
import { Sparkles, RefreshCw, AlertCircle, ChevronDown, ChevronRight } from "lucide-react"
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Card, CardContent } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { SectionHeaderCard } from "./section-header-card"
import { DraftEditor } from "./draft-editor"
import { AISuggestionCard } from "./ai-suggestion-card"
import { DiffConfirmDialog } from "./diff-confirm-dialog"
import { EvidencePanel } from "./evidence-panel"
import { CostStatusBar, type CostStatus } from "./cost-status-bar"
import { AnalyseEinstellungenDialog } from "@/components/run/analyse-einstellungen-dialog"
import {
  portalSections,
  aiSuggestions,
  evidenceAnchors,
  linkableEvidence,
  draftText as initialDraft,
  type AISuggestion,
} from "@/lib/editor-data"

type SuggestionState = "list" | "loading" | "failed" | "off"

interface ProposalEditorProps {
  /** Demo control: cost footer variant. */
  costStatus?: CostStatus
  /** Demo control: KI suggestions state. */
  suggestionState?: SuggestionState
}

export function ProposalEditor({
  costStatus = "ok",
  suggestionState = "list",
}: ProposalEditorProps) {
  const [sectionId, setSectionId] = React.useState(portalSections[0].id)
  // Keep a draft per section so switching doesn't lose work.
  const [drafts, setDrafts] = React.useState<Record<string, string>>({
    [portalSections[0].id]: initialDraft,
  })
  const [activeTab, setActiveTab] = React.useState("entwurf")
  const [diffOpen, setDiffOpen] = React.useState(false)
  const [pending, setPending] = React.useState<AISuggestion | null>(null)
  // After "Anpassen" the accepted text should be edited right away.
  const [editAfterApply, setEditAfterApply] = React.useState(false)
  const [showOlder, setShowOlder] = React.useState(false)

  // Suggestions are local demo state so a run can prepend a new entry.
  const [sugState, setSugState] = React.useState<SuggestionState>(suggestionState)
  const [suggestions, setSuggestions] = React.useState(aiSuggestions)
  const [runDialogOpen, setRunDialogOpen] = React.useState(false)
  const runPurpose = React.useRef<"regenerate" | "activate">("regenerate")
  const runTimer = React.useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  const regenCount = React.useRef(0)

  React.useEffect(() => () => clearTimeout(runTimer.current), [])

  const section = portalSections.find((s) => s.id === sectionId)!
  const draft = drafts[sectionId] ?? ""
  const setDraft = (value: string) =>
    setDrafts((prev) => ({ ...prev, [sectionId]: value }))

  // Live char count: count UTF-16 code units, excluding trailing newlines.
  const liveCharCount = draft.trimEnd().length
  const visibleSuggestions = suggestions.slice(0, 3)
  const olderSuggestions = suggestions.slice(3)

  function applySuggestion(suggestion: AISuggestion, editAfter: boolean) {
    if (draft.trim().length > 0) {
      // Existing text present -> always confirm via diff dialog.
      setPending(suggestion)
      setEditAfterApply(editAfter)
      setDiffOpen(true)
    } else {
      setDraft(suggestion.text.join("\n\n"))
      if (editAfter) setActiveTab("entwurf")
    }
  }

  function handleAccept(suggestion: AISuggestion) {
    applySuggestion(suggestion, false)
  }

  function handleAdjust(suggestion: AISuggestion) {
    applySuggestion(suggestion, true)
  }

  function confirmReplace() {
    if (pending) setDraft(pending.text.join("\n\n"))
    setDiffOpen(false)
    setPending(null)
    if (editAfterApply) {
      setActiveTab("entwurf")
      setEditAfterApply(false)
    }
  }

  function openRunDialog(purpose: "regenerate" | "activate") {
    runPurpose.current = purpose
    setRunDialogOpen(true)
  }

  function handleRunStart() {
    setRunDialogOpen(false)
    setSugState("loading")
    clearTimeout(runTimer.current)
    runTimer.current = setTimeout(() => {
      if (runPurpose.current === "regenerate") {
        regenCount.current += 1
        const fresh: AISuggestion = {
          id: `s-neu-${regenCount.current}`,
          text: [
            "Neuer Vorschlag (Dummy): Die Marktposition lässt sich zusätzlich über regulatorische Treiber im europäischen Raum differenzieren, ohne die bestehende Kostenargumentation zu schwächen.",
          ],
          evidence: [
            { label: "EU-Bericht (Dummy) · S. 21" },
            { label: "Marktstudie (Dummy) · S. 4" },
          ],
        }
        setSuggestions((prev) => [fresh, ...prev])
      }
      setSugState("list")
    }, 1500)
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      <SectionHeaderCard
        section={section}
        sections={portalSections}
        liveCharCount={liveCharCount}
        onSectionChange={setSectionId}
      />

      <div className="flex min-h-0 flex-1">
        {/* Main editor area (~60%) */}
        <div className="flex min-w-0 flex-1 flex-col overflow-y-auto p-6">
          <Tabs
            value={activeTab}
            onValueChange={(value) => setActiveTab(String(value))}
            className="flex min-h-0 flex-1 flex-col"
          >
            <TabsList>
              <TabsTrigger value="entwurf">Entwurf</TabsTrigger>
              <TabsTrigger value="ki">
                {`KI-Vorschläge (${visibleSuggestions.length})`}
              </TabsTrigger>
              <TabsTrigger value="notizen">Notizen</TabsTrigger>
            </TabsList>

            <TabsContent value="entwurf" className="mt-4">
              {draft.trim().length === 0 ? (
                <div className="flex flex-col gap-4">
                  <div className="flex flex-col gap-2 rounded-md border border-dashed border-border bg-muted/30 px-5 py-4">
                    <p className="text-sm text-muted-foreground">
                      {section.guidance}
                    </p>
                    <button
                      type="button"
                      className="self-start text-sm font-medium text-primary underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                      onClick={() => setActiveTab("ki")}
                    >
                      1 KI-Vorschlag verfügbar
                    </button>
                  </div>
                  <DraftEditor draftText={draft} onChange={setDraft} />
                </div>
              ) : (
                <DraftEditor draftText={draft} onChange={setDraft} />
              )}
            </TabsContent>

            <TabsContent value="ki" className="mt-4">
              <SuggestionTab
                state={sugState}
                suggestions={visibleSuggestions}
                olderCount={olderSuggestions.length}
                showOlder={showOlder}
                onToggleOlder={() => setShowOlder((v) => !v)}
                olderSuggestions={olderSuggestions}
                onAccept={handleAccept}
                onAdjust={handleAdjust}
                onRegenerate={() => openRunDialog("regenerate")}
                onActivate={() => openRunDialog("activate")}
              />
            </TabsContent>

            <TabsContent value="notizen" className="mt-4">
              <Textarea
                placeholder="Interne Notizen zu diesem Abschnitt…"
                className="min-h-[320px] resize-y text-sm leading-relaxed"
              />
            </TabsContent>
          </Tabs>
        </div>

        {/* Right evidence panel */}
        <EvidencePanel
          evidence={evidenceAnchors}
          linkCandidates={linkableEvidence}
          unsupportedCount={2}
        />
      </div>

      <CostStatusBar status={costStatus} kiOn webOn={false} />

      <DiffConfirmDialog
        open={diffOpen}
        onOpenChange={setDiffOpen}
        currentText={draft}
        suggestionText={pending?.text.join("\n\n") ?? ""}
        onConfirm={confirmReplace}
      />

      {/* Single-run settings dialog for "Neu erstellen" / one-off KI runs */}
      <AnalyseEinstellungenDialog
        open={runDialogOpen}
        onOpenChange={setRunDialogOpen}
        role="lead_admin"
        dataClass="public"
        variant="compact"
        onStart={handleRunStart}
        onCancel={() => setRunDialogOpen(false)}
      />
    </div>
  )
}

interface SuggestionTabProps {
  state: SuggestionState
  suggestions: AISuggestion[]
  olderSuggestions: AISuggestion[]
  olderCount: number
  showOlder: boolean
  onToggleOlder: () => void
  onAccept: (s: AISuggestion) => void
  onAdjust: (s: AISuggestion) => void
  onRegenerate: (s: AISuggestion) => void
  onActivate: () => void
}

function SuggestionTab({
  state,
  suggestions,
  olderSuggestions,
  olderCount,
  showOlder,
  onToggleOlder,
  onAccept,
  onAdjust,
  onRegenerate,
  onActivate,
}: SuggestionTabProps) {
  if (state === "off") {
    return (
      <div className="flex flex-col items-start gap-3 rounded-md border border-border bg-muted/30 p-6">
        <p className="text-sm text-muted-foreground">
          KI-Unterstützung ist ausgeschaltet. Dieser Abschnitt enthält
          strukturierte Hinweise ohne KI-Vorschläge.
        </p>
        <Button variant="outline" size="sm" onClick={onActivate}>
          <Sparkles data-icon="inline-start" />
          KI für einen Durchlauf aktivieren
        </Button>
      </div>
    )
  }

  if (state === "loading") {
    return (
      <Card>
        <CardContent className="flex flex-col gap-3 pt-6">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <RefreshCw className="size-4 animate-spin" />
            Vorschlag wird erstellt — Belege werden verknüpft…
          </div>
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-11/12" />
          <Skeleton className="h-4 w-4/5" />
        </CardContent>
      </Card>
    )
  }

  if (state === "failed") {
    return (
      <div className="flex flex-col items-start gap-3 rounded-md border border-destructive/30 bg-destructive/5 p-6">
        <div className="flex items-center gap-2 text-sm font-medium text-destructive">
          <AlertCircle className="size-4" />
          Vorschlag konnte nicht erstellt werden.
        </div>
        <Button variant="outline" size="sm">
          <RefreshCw data-icon="inline-start" />
          Erneut versuchen
        </Button>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-3">
      {suggestions.map((s) => (
        <AISuggestionCard
          key={s.id}
          suggestion={s}
          onAccept={onAccept}
          onAdjust={onAdjust}
          onRegenerate={onRegenerate}
        />
      ))}

      {olderCount > 0 && (
        <div className="flex flex-col gap-3">
          <button
            type="button"
            onClick={onToggleOlder}
            className="flex items-center gap-1.5 self-start rounded text-sm font-medium text-muted-foreground underline-offset-2 outline-none hover:text-foreground hover:underline focus-visible:ring-2 focus-visible:ring-ring"
          >
            {showOlder ? (
              <ChevronDown className="size-4" />
            ) : (
              <ChevronRight className="size-4" />
            )}
            {`Ältere Vorschläge (${olderCount})`}
          </button>
          {showOlder &&
            olderSuggestions.map((s) => (
              <AISuggestionCard
                key={s.id}
                suggestion={s}
                onAccept={onAccept}
                onAdjust={onAdjust}
                onRegenerate={onRegenerate}
              />
            ))}
        </div>
      )}
    </div>
  )
}
