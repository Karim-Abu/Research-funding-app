"use client"

import * as React from "react"
import { Save, Sparkles, AlertTriangle, Check, X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { cn } from "@/lib/utils"
import { charCount } from "@/lib/fields"
import {
  charLimitInfo,
  hasPlaceholder,
  firstPlaceholderIndex,
  DRAFT_STATUS_LABELS,
  DRAFT_FALLBACK,
  OVER_LIMIT_WARNING,
  PLACEHOLDER_TITLE,
  PLACEHOLDER_PROBLEM,
  type DraftFieldStatus,
} from "@/lib/draft-view"
import { AI_PRIMARY } from "@/lib/draft-ai-actions"
import { isMarketRelevantFieldId, type DraftFieldViewModel } from "@/lib/draft-viewmodel"

export interface DraftWorkspaceSuggestion {
  text: string
  improvements: string[]
}

type MobileView = "felder" | "text" | "ki" | "kontext"

const STATUS_DOT: Record<DraftFieldStatus, string> = {
  ready: "bg-status-fulfilled",
  needs_review: "bg-status-partial",
  no_evidence: "bg-status-partial",
  blocked: "bg-destructive",
  open: "bg-muted-foreground/40",
}

interface DraftWorkspaceShellProps {
  subtitle: string
  viewModels: DraftFieldViewModel[]
  selectedId: string
  onSelect: (id: string) => void
  activeVm: DraftFieldViewModel

  text: string
  onChangeText: (value: string) => void
  onSave: () => void
  saveDisabled: boolean
  saveStateLabel: string
  deinTextBadge?: React.ReactNode
  deinTextHint?: React.ReactNode
  noticeSlot?: React.ReactNode
  marketHeaderLabel?: string

  aiActions: { key: string; label: string }[]
  aiEnabled: boolean
  aiHint?: string
  onAiAction: (key: string) => void
  suggestion: DraftWorkspaceSuggestion | null
  onAcceptAll: () => void
  onAcceptParagraph: () => void
  onToggleCompare: () => void
  compareOpen: boolean
  onDiscard: () => void

  assistant: React.ReactNode
  conflictDialog?: React.ReactNode
  footer?: React.ReactNode
}

export function DraftWorkspaceShell(props: DraftWorkspaceShellProps) {
  const {
    subtitle,
    viewModels,
    selectedId,
    onSelect,
    activeVm,
    text,
    onChangeText,
    onSave,
    saveDisabled,
    saveStateLabel,
    deinTextBadge,
    deinTextHint,
    noticeSlot,
    marketHeaderLabel,
    aiActions,
    aiEnabled,
    aiHint,
    onAiAction,
    suggestion,
    onAcceptAll,
    onAcceptParagraph,
    onToggleCompare,
    compareOpen,
    onDiscard,
    assistant,
    conflictDialog,
    footer,
  } = props

  const [view, setView] = React.useState<MobileView>("text")
  const textareaRef = React.useRef<HTMLTextAreaElement>(null)

  const count = charCount(text)
  const limitInfo = charLimitInfo(count, activeVm.characterLimit)
  const showPlaceholder = hasPlaceholder(text)
  const portalPath = `${activeVm.sectionLabel} › ${activeVm.fieldLabel}`

  function selectField(id: string) {
    onSelect(id)
    setView("text")
  }

  function jumpToPlaceholder() {
    const index = firstPlaceholderIndex(text)
    const node = textareaRef.current
    if (index < 0 || !node) return
    setView("text")
    node.focus()
    node.setSelectionRange(index, index)
    const before = text.slice(0, index).split("\n").length
    node.scrollTop = Math.max(0, (before - 2) * 20)
  }

  const sections: { label: string; items: DraftFieldViewModel[] }[] = []
  for (const vm of viewModels) {
    let group = sections.find((s) => s.label === vm.sectionLabel)
    if (!group) {
      group = { label: vm.sectionLabel, items: [] }
      sections.push(group)
    }
    group.items.push(vm)
  }

  // KI action controls (primary + goal chips), rendered inside the KI pane.
  const kiActions = (
    <div className="flex flex-col gap-2">
      <Button size="sm" disabled={!aiEnabled} onClick={() => onAiAction(AI_PRIMARY.key)} className="self-start">
        <Sparkles className="mr-1.5 size-3.5" />
        {AI_PRIMARY.label}
      </Button>
      <div className="flex flex-col gap-1">
        <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
          Ziel des Vorschlags
        </p>
        <div className="flex flex-wrap gap-1.5">
          {aiActions.map((a) => (
            <button
              key={a.key}
              type="button"
              disabled={!aiEnabled}
              onClick={() => onAiAction(a.key)}
              className={cn(
                "inline-flex items-center rounded-full border px-2.5 py-1 text-[11px] font-medium transition-colors",
                aiEnabled
                  ? "border-border bg-card text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                  : "border-border bg-muted/40 text-muted-foreground/60"
              )}
            >
              {a.label}
            </button>
          ))}
        </div>
      </div>
      {!aiEnabled && aiHint && <p className="text-[11px] text-muted-foreground">{aiHint}</p>}
    </div>
  )

  return (
    <div className="flex min-h-full flex-col">
      <div className="flex-1 px-6 py-6 pb-28">
        <div className="mx-auto max-w-[1400px]">
          {/* Single page header */}
          <div className="mb-6 flex flex-col gap-1">
            <h1 className="text-balance text-2xl font-semibold text-foreground">Antragsentwurf</h1>
            <p className="text-sm text-muted-foreground">{subtitle}</p>
          </div>

          {/* Mobile view switch */}
          <div className="mb-4 grid grid-cols-4 gap-2 lg:hidden">
            {(
              [
                ["felder", "Felder"],
                ["text", "Text"],
                ["ki", "KI-Vorschlag"],
                ["kontext", "Kontext"],
              ] as [MobileView, string][]
            ).map(([key, label]) => (
              <button
                key={key}
                type="button"
                onClick={() => setView(key)}
                className={cn(
                  "inline-flex h-8 items-center justify-center rounded-md border px-1 text-[11px] font-medium",
                  view === key
                    ? "border-primary bg-primary/10 text-primary"
                    : "border-border bg-card text-muted-foreground"
                )}
              >
                {label}
              </button>
            ))}
          </div>

          <div className="lg:grid lg:grid-cols-[300px_minmax(0,1fr)] lg:gap-6 xl:grid-cols-[300px_minmax(0,1fr)_360px]">
            {/* Left: portal field navigation */}
            <nav
              aria-label="Portal-Felder"
              className={cn("flex-col gap-5 lg:flex", view === "felder" ? "flex" : "hidden")}
            >
              {sections.map((section) => (
                <div key={section.label} className="flex flex-col gap-1">
                  <p className="px-1 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                    {section.label}
                  </p>
                  {section.items.map((vm) => (
                    <FieldNavButton
                      key={vm.id}
                      vm={vm}
                      active={vm.id === selectedId}
                      onSelect={() => selectField(vm.id)}
                    />
                  ))}
                </div>
              ))}
            </nav>

            {/* Middle: editing region */}
            <div
              className={cn(
                "min-w-0 flex-col gap-5 lg:flex",
                view === "text" || view === "ki" ? "flex" : "hidden"
              )}
            >
              {/* Field header */}
              <div className="flex flex-col gap-1.5">
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="text-lg font-semibold text-foreground">{portalPath}</h2>
                  <FieldStatusBadge status={activeVm.status} />
                </div>
                {activeVm.helperLabel && (
                  <p className="text-xs text-muted-foreground">{activeVm.helperLabel}</p>
                )}
                <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
                  <span className={limitInfo.className}>{limitInfo.text}</span>
                  <span aria-hidden>·</span>
                  <span>{activeVm.evidenceCount} Belege</span>
                  <span aria-hidden>·</span>
                  <span>{activeVm.openIssueCount} offene Punkte</span>
                  <span aria-hidden>·</span>
                  <span>{activeVm.commentCount} Kommentare</span>
                  {marketHeaderLabel && (
                    <>
                      <span aria-hidden>·</span>
                      <span>{marketHeaderLabel}</span>
                    </>
                  )}
                </p>
              </div>

              {/* Two panes */}
              <div className="grid gap-4 lg:grid-cols-2">
                {/* Dein Text */}
                <section className={cn("flex flex-col gap-2", view === "text" ? "flex" : "hidden", "lg:flex")}>
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <h3 className="text-sm font-semibold text-foreground">Dein Text</h3>
                      {deinTextBadge}
                    </div>
                    <span className="text-[11px] text-muted-foreground">{saveStateLabel}</span>
                  </div>
                  {deinTextHint}
                  {limitInfo.state === "over" && (
                    <p
                      role="alert"
                      className="flex items-start gap-1.5 rounded-md border border-destructive/20 bg-destructive/5 px-2.5 py-1.5 text-[11px] text-destructive"
                    >
                      <AlertTriangle className="mt-0.5 size-3 shrink-0" />
                      {OVER_LIMIT_WARNING}
                    </p>
                  )}
                  {showPlaceholder && (
                    <div className="flex flex-wrap items-center gap-x-2 gap-y-1 rounded-md border border-status-partial/25 bg-status-partial/8 px-2.5 py-1.5 text-[11px]">
                      <span className="font-semibold text-status-partial">{PLACEHOLDER_TITLE}</span>
                      <span className="text-muted-foreground">{PLACEHOLDER_PROBLEM}</span>
                      <button
                        type="button"
                        onClick={jumpToPlaceholder}
                        className="font-medium text-primary hover:underline"
                      >
                        Zum Platzhalter springen
                      </button>
                    </div>
                  )}
                  <Textarea
                    ref={textareaRef}
                    value={text}
                    onChange={(e) => onChangeText(e.target.value)}
                    rows={18}
                    aria-label={`Entwurf ${activeVm.fieldLabel}`}
                    placeholder={DRAFT_FALLBACK.noDraft}
                    className="text-sm leading-relaxed"
                  />
                  {noticeSlot}
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-[11px] text-muted-foreground">
                      {activeVm.lastEditedLabel ?? DRAFT_FALLBACK.noEditor}
                    </span>
                    <Button size="sm" onClick={onSave} disabled={saveDisabled}>
                      <Save className="mr-1.5 size-3.5" />
                      Speichern
                    </Button>
                  </div>
                </section>

                {/* KI-Vorschlag */}
                <section className={cn("flex flex-col gap-3", view === "ki" ? "flex" : "hidden", "lg:flex")}>
                  <h3 className="text-sm font-semibold text-foreground">KI-Vorschlag</h3>
                  {kiActions}
                  {!suggestion ? (
                    <div className="rounded-md border border-dashed border-border bg-muted/20 px-4 py-5">
                      <p className="text-sm font-medium text-foreground">Noch kein Vorschlag erstellt</p>
                      <p className="text-xs text-muted-foreground">
                        Wählen Sie ein Ziel, um einen Verbesserungsvorschlag für dieses Feld vorzubereiten.
                      </p>
                    </div>
                  ) : (
                    <div className="flex flex-col gap-3">
                      <div className="max-h-[320px] overflow-auto whitespace-pre-wrap rounded-md border border-border bg-muted/20 px-3 py-2 text-sm leading-relaxed text-foreground">
                        {suggestion.text}
                      </div>
                      {suggestion.improvements.length > 0 && (
                        <div className="flex flex-col gap-1">
                          <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                            Verbesserungen
                          </p>
                          <ul className="flex flex-wrap gap-1.5">
                            {suggestion.improvements.map((imp) => (
                              <li
                                key={imp}
                                className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2 py-0.5 text-[11px] font-medium text-primary"
                              >
                                <Check className="size-3" />
                                {imp}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                      {compareOpen && (
                        <p className="rounded-md border border-border bg-card px-3 py-2 text-[11px] text-muted-foreground">
                          Vergleich: Ihr Text hat {count} Zeichen, der Vorschlag{" "}
                          {charCount(suggestion.text)} Zeichen ({charCount(suggestion.text) - count >= 0 ? "+" : ""}
                          {charCount(suggestion.text) - count}).
                        </p>
                      )}
                      <div className="flex flex-wrap gap-2">
                        <Button size="sm" onClick={onAcceptAll}>Gesamten Vorschlag übernehmen</Button>
                        <Button size="sm" variant="outline" onClick={onAcceptParagraph}>Absatzweise übernehmen</Button>
                        <Button size="sm" variant="ghost" onClick={onToggleCompare}>Änderungen vergleichen</Button>
                        <Button size="sm" variant="ghost" onClick={onDiscard}>
                          <X className="mr-1 size-3.5" />
                          Verwerfen
                        </Button>
                      </div>
                    </div>
                  )}
                </section>
              </div>
            </div>

            {/* Right: assistant panel (below at lg, side column at xl) */}
            <aside
              aria-label="Assistent"
              className={cn(
                "flex-col gap-3 lg:flex lg:col-span-2 xl:col-span-1",
                view === "kontext" ? "flex" : "hidden"
              )}
            >
              {assistant}
            </aside>
          </div>
        </div>
      </div>

      {footer}
      {conflictDialog}
    </div>
  )
}

// ---------------------------------------------------------------------------
function FieldStatusBadge({ status }: { status: DraftFieldStatus }) {
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center rounded-full px-2 py-0.5 text-xs font-medium",
        status === "blocked"
          ? "bg-destructive/10 text-destructive"
          : "bg-muted text-muted-foreground"
      )}
    >
      {DRAFT_STATUS_LABELS[status]}
    </span>
  )
}

function FieldNavButton({
  vm,
  active,
  onSelect,
}: {
  vm: DraftFieldViewModel
  active: boolean
  onSelect: () => void
}) {
  const charText = vm.characterLimit != null ? `${charCount(vm.text)} / ${vm.characterLimit}` : null
  const isBlocked = vm.status === "blocked"
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-current={active ? "true" : undefined}
      className={cn(
        "flex items-center gap-2 rounded-md border px-3 py-2 text-left transition-colors",
        active ? "border-primary/40 bg-accent" : "border-transparent hover:bg-accent/50"
      )}
    >
      <span
        className={cn(
          "shrink-0 rounded-full",
          STATUS_DOT[vm.status],
          isBlocked ? "size-2 ring-2 ring-destructive/20" : "size-1.5"
        )}
        title={DRAFT_STATUS_LABELS[vm.status]}
        aria-label={DRAFT_STATUS_LABELS[vm.status]}
      />
      <span className="flex min-w-0 flex-1 flex-col">
        <span className="truncate text-sm font-medium text-foreground">{vm.fieldLabel}</span>
        <span className="flex items-center gap-2">
          {charText && <span className="text-[11px] text-muted-foreground">{charText}</span>}
          {isMarketRelevantFieldId(vm.id) && (
            <span
              className="size-1.5 shrink-0 rounded-full bg-primary/50"
              title="Marktbezug"
              aria-label="Marktbezug"
            />
          )}
        </span>
      </span>
      {isBlocked && (
        <span className="shrink-0 text-[10px] font-semibold uppercase tracking-wide text-destructive">
          Blocker
        </span>
      )}
    </button>
  )
}
