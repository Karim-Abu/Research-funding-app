"use client"

import * as React from "react"
import {
  Save,
  Sparkles,
  AlertTriangle,
  Check,
  X,
  PanelLeftClose,
  PanelLeftOpen,
  PanelRightClose,
  PanelRightOpen,
  Maximize2,
  Minimize2,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  RichTextEditor,
  type RichTextEditorHandle,
} from "@/components/editor/rich-text-editor"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { cn } from "@/lib/utils"
import { charCount } from "@/lib/fields"
import {
  charLimitInfo,
  placeholderMatches,
  placeholderCountText,
  DRAFT_STATUS_LABELS,
  DRAFT_FALLBACK,
  OVER_LIMIT_WARNING,
  PLACEHOLDER_TITLE,
  type DraftFieldStatus,
} from "@/lib/draft-view"
import { AI_PRIMARY } from "@/lib/draft-ai-actions"
import { isMarketRelevantFieldId, type DraftFieldViewModel } from "@/lib/draft-viewmodel"

export interface DraftWorkspaceSuggestion {
  text: string
  improvements: string[]
}

// Three explicit work modes for the Entwurf workspace. `bearbeiten` is the
// default so the editor textarea, badge, hint, counter and Speichern button are
// always present on first render (relied on by the live-editor tests + the
// real-browser e2e smoke). Modes only change layout/visibility via CSS — they
// never unmount test-critical elements.
type WorkspaceMode = "bearbeiten" | "ki" | "pruefen"

const MODES: { key: WorkspaceMode; label: string; hint: string }[] = [
  {
    key: "bearbeiten",
    label: "Bearbeiten",
    hint: "Großer Editor — KI-Vorschlag und Kontext treten in den Hintergrund.",
  },
  {
    key: "ki",
    label: "KI-Assist",
    hint: "Dein Text und KI-Vorschlag nebeneinander. Vorschläge werden nie automatisch übernommen.",
  },
  {
    key: "pruefen",
    label: "Prüfen",
    hint: "Belege, Anforderungen, Kommentare und Freigabe im Kontextpanel.",
  },
]

const STATUS_DOT: Record<DraftFieldStatus, string> = {
  ready: "bg-status-fulfilled",
  needs_review: "bg-status-partial",
  no_evidence: "bg-status-partial",
  blocked: "bg-destructive",
  open: "bg-muted-foreground/40",
}

// Browser spellcheck for the editor textarea. Proposals are written in German
// or English, so the language (and off) is a per-session user preference.
type SpellSetting = "de" | "en" | "off"

const SPELL_KEY = "rf_editor_spellcheck"

const SPELL_OPTIONS: { key: SpellSetting; label: string; hint: string }[] = [
  { key: "de", label: "Deutsch", hint: "Browser-Rechtschreibprüfung auf Deutsch" },
  { key: "en", label: "Englisch", hint: "Browser-Rechtschreibprüfung auf Englisch" },
  { key: "off", label: "Aus", hint: "Rechtschreibprüfung deaktivieren" },
]

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
  /** Owner-supplied handle so the container can jump/insert in the editor. */
  editorRef?: React.RefObject<RichTextEditorHandle | null>
  /**
   * Persisted server plain text used to (re)initialise the rich editor per
   * field. Defaults to `text` (mock). Live passes the current version text so
   * typing doesn't re-init the editor.
   */
  serverText?: string
  /** Active project id — enables the per-session formatting cache. */
  projectId?: string
  /** Data class of the project; restricted classes disable the cache. */
  dataClass?: string | null

  /**
   * When set, the KI-Vorschlag pane renders this instead of the mock
   * goal-chip UI below (live mode supplies the real A2 suggestion flow).
   */
  kiContent?: React.ReactNode

  // Mock-only KI suggestion API (unused when kiContent is provided).
  aiActions?: { key: string; label: string }[]
  aiEnabled?: boolean
  aiHint?: string
  onAiAction?: (key: string) => void
  suggestion?: DraftWorkspaceSuggestion | null
  onAcceptAll?: () => void
  onAcceptParagraph?: () => void
  onToggleCompare?: () => void
  compareOpen?: boolean
  onDiscard?: () => void

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
    editorRef: externalEditorRef,
    serverText,
    projectId,
    dataClass,
    kiContent,
    aiActions = [],
    aiEnabled = false,
    aiHint,
    onAiAction,
    suggestion = null,
    onAcceptAll,
    onAcceptParagraph,
    onToggleCompare,
    compareOpen = false,
    onDiscard,
    assistant,
    conflictDialog,
    footer,
  } = props

  const [mode, setMode] = React.useState<WorkspaceMode>("bearbeiten")
  const [navCollapsed, setNavCollapsed] = React.useState(false)
  // null = mode-dependent default: collapsed while writing (Bearbeiten +
  // KI-Assist), open in Prüfen. A click stores an explicit user override.
  const [contextOverride, setContextOverride] = React.useState<boolean | null>(null)
  const [focus, setFocus] = React.useState(false)
  const [spell, setSpell] = React.useState<SpellSetting>("de")
  const [placeholderCursor, setPlaceholderCursor] = React.useState(0)
  const internalEditorRef = React.useRef<RichTextEditorHandle>(null)
  const editorRef = externalEditorRef ?? internalEditorRef

  // Hydrate the spellcheck preference after mount (SSR-safe, storage may be
  // blocked by privacy settings).
  React.useEffect(() => {
    try {
      const stored = window.sessionStorage.getItem(SPELL_KEY)
      if (stored === "de" || stored === "en" || stored === "off") setSpell(stored)
    } catch {
      /* storage blocked */
    }
  }, [])

  function changeSpell(next: SpellSetting) {
    setSpell(next)
    try {
      window.sessionStorage.setItem(SPELL_KEY, next)
    } catch {
      /* storage blocked */
    }
  }

  // Restart placeholder cycling when another field is opened.
  React.useEffect(() => setPlaceholderCursor(0), [selectedId])

  const count = charCount(text)
  const limitInfo = charLimitInfo(count, activeVm.characterLimit)
  const placeholders = placeholderMatches(text)
  const showPlaceholder = placeholders.length > 0
  const portalPath = `${activeVm.sectionLabel} › ${activeVm.fieldLabel}`

  // Explain why the Speichern button is disabled (P0 requirement #6). Derived
  // from the label + limit state so it works for both the live and mock editors.
  const overLimit = limitInfo.state === "over"
  let saveReason: string | null = null
  if (saveDisabled) {
    // Anchored so the saving label ("Speichert …") matches but the saved label
    // ("Gespeichert") does not — the latter means "no unsaved changes".
    if (overLimit) saveReason = "Text über dem Zeichenlimit — bitte kürzen."
    else if (/^speichert/i.test(saveStateLabel.trim())) saveReason = "Wird gerade gespeichert …"
    else saveReason = "Keine ungespeicherten Änderungen."
  }
  const aiDisabledHint = !aiEnabled ? aiHint : undefined

  // The context panel is always shown while in Prüfen mode; in the writing
  // modes it starts collapsed (calm editor) until the user overrides it.
  const contextCollapsed = contextOverride ?? mode !== "pruefen"
  const contextHidden = contextCollapsed && mode !== "pruefen"
  const editorMinH = focus
    ? "min-h-[76vh]!"
    : mode === "ki"
      ? "min-h-[52vh]!"
      : "min-h-[60vh]!"

  // Select the current placeholder (visible marking in the editor), then advance
  // so a repeated click walks through all placeholders. Detection/count stay on
  // the plain text; the editor jump is best-effort (see RichTextEditor).
  function jumpToPlaceholder() {
    if (placeholders.length === 0) return
    editorRef.current?.selectPlaceholder(placeholderCursor % placeholders.length)
    setPlaceholderCursor((i) => (i + 1) % placeholders.length)
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

  const saveButton = (
    <Button
      size="sm"
      onClick={onSave}
      disabled={saveDisabled}
      title={saveReason ?? "Speichern (Strg+S)"}
    >
      <Save className="mr-1.5 size-3.5" />
      Speichern
    </Button>
  )

  // KI action controls (primary + goal chips), rendered inside the KI pane.
  const kiActions = (
    <div className="flex flex-col gap-2">
      <Button
        size="sm"
        disabled={!aiEnabled}
        onClick={() => onAiAction?.(AI_PRIMARY.key)}
        className="self-start"
        title={aiDisabledHint}
      >
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
              onClick={() => onAiAction?.(a.key)}
              title={aiDisabledHint}
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
      {!aiEnabled && aiHint && (
        <p className="flex items-start gap-1.5 rounded-md border border-border bg-muted/30 px-2.5 py-1.5 text-[11px] text-muted-foreground">
          <Sparkles className="mt-0.5 size-3 shrink-0" />
          {aiHint}
        </p>
      )}
    </div>
  )

  return (
    <TooltipProvider>
      <div className="flex min-h-full flex-col" data-mode={mode} data-focus={focus || undefined}>
        <div className="flex-1 px-6 py-6 pb-28">
          <div className="mx-auto max-w-[1600px]">
            {/* Focus mode replaces the header + toolbar with a compact top bar. */}
            {focus ? (
              <div className="mb-5 flex flex-wrap items-center gap-3 rounded-lg border border-border bg-card px-4 py-2.5 shadow-sm">
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-foreground">
                    {activeVm.fieldLabel}
                  </p>
                  <p className={cn("text-xs", limitInfo.className)}>{limitInfo.text}</p>
                </div>
                <div className="ml-auto flex items-center gap-2">
                  {saveReason && (
                    <span className="hidden text-[11px] text-muted-foreground sm:inline">
                      {saveReason}
                    </span>
                  )}
                  {saveButton}
                  <Button variant="ghost" size="sm" onClick={() => setFocus(false)}>
                    <Minimize2 className="mr-1.5 size-3.5" />
                    Fokus verlassen
                  </Button>
                </div>
              </div>
            ) : (
              <>
                <div className="mb-4 flex flex-col gap-1">
                  <h1 className="text-balance text-2xl font-semibold text-foreground">
                    Antragsentwurf
                  </h1>
                  <p className="text-sm text-muted-foreground">{subtitle}</p>
                </div>

                <div className="mb-5 flex flex-wrap items-center gap-2">
                  <div
                    role="group"
                    aria-label="Ansichtsmodus"
                    className="inline-flex items-center gap-0.5 rounded-lg border border-border bg-card p-0.5"
                  >
                    {MODES.map((m) => (
                      <Button
                        key={m.key}
                        size="sm"
                        variant={mode === m.key ? "default" : "ghost"}
                        aria-pressed={mode === m.key}
                        onClick={() => setMode(m.key)}
                        title={m.hint}
                      >
                        {m.label}
                      </Button>
                    ))}
                  </div>
                  <div className="ml-auto flex flex-wrap items-center gap-2">
                    <div
                      role="group"
                      aria-label="Rechtschreibprüfung"
                      className="inline-flex items-center gap-0.5 rounded-lg border border-border bg-card p-0.5"
                    >
                      <span className="px-1.5 text-[11px] text-muted-foreground">
                        Rechtschreibung
                      </span>
                      {SPELL_OPTIONS.map((o) => (
                        <Button
                          key={o.key}
                          size="xs"
                          variant={spell === o.key ? "secondary" : "ghost"}
                          aria-pressed={spell === o.key}
                          onClick={() => changeSpell(o.key)}
                          title={o.hint}
                        >
                          {o.label}
                        </Button>
                      ))}
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setFocus(true)}
                      title="Ablenkungsfreier Editor über die volle Breite"
                    >
                      <Maximize2 className="mr-1.5 size-3.5" />
                      Fokus
                    </Button>
                  </div>
                </div>
              </>
            )}

            <div className={cn("flex flex-col gap-6", !focus && "lg:flex-row")}>
              {/* Left: portal field navigation (collapsible; hidden in focus) */}
              <nav
                aria-label="Portal-Felder"
                className={cn(
                  "shrink-0",
                  focus && "hidden",
                  navCollapsed ? "lg:w-12" : "lg:w-[260px]"
                )}
              >
                {/* Expanded navigation */}
                <div className={cn("flex-col gap-5", navCollapsed ? "hidden" : "flex")}>
                  <div className="flex items-center justify-between gap-2 px-1">
                    <span className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                      Felder
                    </span>
                    <Tooltip>
                      <TooltipTrigger
                        render={
                          <Button
                            variant="ghost"
                            size="icon-sm"
                            aria-label="Feldnavigation einklappen"
                            onClick={() => setNavCollapsed(true)}
                          />
                        }
                      >
                        <PanelLeftClose className="size-4" />
                      </TooltipTrigger>
                      <TooltipContent>Feldnavigation einklappen</TooltipContent>
                    </Tooltip>
                  </div>
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
                          onSelect={() => onSelect(vm.id)}
                        />
                      ))}
                    </div>
                  ))}
                </div>
                {/* Collapsed rail */}
                <div className={cn("justify-center", navCollapsed ? "flex" : "hidden")}>
                  <Tooltip>
                    <TooltipTrigger
                      render={
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          aria-label="Feldnavigation einblenden"
                          onClick={() => setNavCollapsed(false)}
                        />
                      }
                    >
                      <PanelLeftOpen className="size-4" />
                    </TooltipTrigger>
                    <TooltipContent>Feldnavigation einblenden</TooltipContent>
                  </Tooltip>
                </div>
              </nav>

              {/* Middle: editing region */}
              <div className="flex min-w-0 flex-1 flex-col gap-5">
                {/* Field header (hidden in focus — the focus bar carries it) */}
                <div className={cn("flex flex-col gap-1.5", focus && "hidden")}>
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

                {/* Panes: Dein Text always visible; KI-Vorschlag only in KI-Assist. */}
                <div
                  className={cn(
                    "grid gap-4",
                    mode === "ki" ? "grid-cols-1 lg:grid-cols-2" : "grid-cols-1"
                  )}
                >
                  {/* Dein Text */}
                  <section className="flex flex-col gap-2">
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
                        <span className="text-muted-foreground">
                          {placeholderCountText(placeholders.length)}
                        </span>
                        <button
                          type="button"
                          onClick={jumpToPlaceholder}
                          className="font-medium text-primary hover:underline"
                        >
                          {placeholders.length > 1
                            ? "Nächster Platzhalter"
                            : "Platzhalter markieren"}
                        </button>
                      </div>
                    )}
                    <RichTextEditor
                      ref={editorRef}
                      fieldKey={selectedId}
                      serverText={serverText ?? text}
                      projectId={projectId}
                      dataClass={dataClass}
                      fieldLabel={activeVm.fieldLabel}
                      placeholder={DRAFT_FALLBACK.noDraft}
                      spell={spell}
                      minHeightClass={editorMinH}
                      onChange={onChangeText}
                      onSave={onSave}
                      saveDisabled={saveDisabled}
                    />
                    <p className="flex flex-wrap items-center gap-x-1.5 gap-y-0.5 text-[11px] text-muted-foreground">
                      <span>
                        Formatierungen werden während der Sitzung gespeichert. Innolink übernimmt
                        beim Kopieren reinen Text; Listen und Absätze bleiben erhalten.
                      </span>
                      <button
                        type="button"
                        onClick={() => editorRef.current?.clearFormatCache()}
                        className="font-medium text-primary hover:underline"
                      >
                        Format-Zwischenspeicher löschen
                      </button>
                    </p>
                    {noticeSlot}
                    <div
                      className={cn(
                        "flex flex-wrap items-center justify-between gap-2",
                        focus && "hidden"
                      )}
                    >
                      <div className="flex min-w-0 items-center gap-2">
                        <span className="truncate text-[11px] text-muted-foreground">
                          {activeVm.lastEditedLabel ?? DRAFT_FALLBACK.noEditor}
                        </span>
                        <Button
                          variant="ghost"
                          size="xs"
                          onClick={() => setMode("ki")}
                          className={cn("shrink-0", mode !== "bearbeiten" && "hidden")}
                        >
                          <Sparkles className="mr-1 size-3" />
                          KI-Assist öffnen
                        </Button>
                      </div>
                      <div className="flex items-center gap-2">
                        {saveReason && (
                          <span className="text-[11px] text-muted-foreground">{saveReason}</span>
                        )}
                        {saveButton}
                      </div>
                    </div>
                  </section>

                  {/* KI-Vorschlag */}
                  <section
                    className={cn(
                      "flex-col gap-3",
                      mode === "ki" ? "flex" : "hidden"
                    )}
                  >
                    <h3 className="text-sm font-semibold text-foreground">KI-Vorschlag</h3>
                    {/* Live supplies kiContent (real A2 flow); mock falls back
                        to the simulated goal-chip suggestion UI below. */}
                    {kiContent ?? (
                      <>
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
                      </>
                    )}
                  </section>
                </div>
              </div>

              {/* Right: assistant panel (collapsible; prominent in Prüfen; hidden in focus) */}
              <aside
                aria-label="Assistent"
                className={cn(
                  "shrink-0",
                  focus && "hidden",
                  mode === "pruefen"
                    ? "lg:w-[380px] xl:w-[440px]"
                    : contextCollapsed
                      ? "lg:w-12"
                      : "lg:w-[360px]"
                )}
              >
                {/* Collapsed rail (only outside Prüfen) */}
                <div className={cn("justify-center", contextHidden ? "flex" : "hidden")}>
                  <Tooltip>
                    <TooltipTrigger
                      render={
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          aria-label="Kontextpanel einblenden"
                          onClick={() => setContextOverride(false)}
                        />
                      }
                    >
                      <PanelRightOpen className="size-4" />
                    </TooltipTrigger>
                    <TooltipContent>Kontextpanel einblenden</TooltipContent>
                  </Tooltip>
                </div>
                {/* Expanded body — always mounted; CSS-hidden when collapsed. */}
                <div className={cn("flex-col gap-3", contextHidden ? "hidden" : "flex")}>
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                      {mode === "pruefen" ? "Prüfen" : "Kontext"}
                    </span>
                    {mode !== "pruefen" && (
                      <Tooltip>
                        <TooltipTrigger
                          render={
                            <Button
                              variant="ghost"
                              size="icon-sm"
                              aria-label="Kontextpanel einklappen"
                              onClick={() => setContextOverride(true)}
                            />
                          }
                        >
                          <PanelRightClose className="size-4" />
                        </TooltipTrigger>
                        <TooltipContent>Kontextpanel einklappen</TooltipContent>
                      </Tooltip>
                    )}
                  </div>
                  {assistant}
                </div>
              </aside>
            </div>
          </div>
        </div>

        {footer}
        {conflictDialog}
      </div>
    </TooltipProvider>
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
