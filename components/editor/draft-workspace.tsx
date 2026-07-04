"use client"

import * as React from "react"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { cn } from "@/lib/utils"
import { charCount } from "@/lib/fields"
import { hasPlaceholder } from "@/lib/draft-view"
import {
  DraftWorkspaceShell,
  type DraftWorkspaceSuggestion,
} from "@/components/editor/draft-workspace-shell"
import { AssistantPanel } from "@/components/editor/assistant-panel"
import {
  sectionLabelFromFieldId,
  isMarketRelevantFieldId,
  pickDefaultTab,
  helperLabel,
  type DraftFieldViewModel,
} from "@/lib/draft-viewmodel"
import { AI_GOALS } from "@/lib/draft-ai-actions"
import { MARKET_STATUS_LABELS, type MarketDataset, type MarketStatus } from "@/lib/market-view"
import {
  draftFields,
  mockMarketBySection,
  mockCommentsByField,
  mockVersionsByField,
  mockResponsibleByField,
  mockReviewerByField,
  type DraftComment,
} from "@/lib/draft-mock-data"

const CURRENT_USER = { name: "Anna Keller", initials: "AK" }

const HEADER_MARKET_LABEL: Record<MarketStatus, string> = {
  belegt: "Marktanalyse belegt",
  teilweise_belegt: "Marktanalyse teilweise belegt",
  quelle_fehlt: "Marktanalyse: Quelle fehlt",
  pruefung_noetig: "Konkurrenzabgrenzung prüfen",
  veraltet: "Marktanalyse veraltet",
  nicht_analysiert: "Marktanalyse fehlt",
}

function appendParagraph(text: string, addition: string): string {
  return text.trim() ? `${text.trim()}\n\n${addition}` : addition
}
function marketSentence(market: MarketDataset | null): string {
  const diff = market?.differentiation.find((d) => d.status === "belegt") ?? market?.differentiation[0]
  if (diff) return `${diff.whatIsDifferent}. ${diff.whyRelevant}.`
  return "Die Lösung adressiert einen wachsenden Markt mit klar benennbarem Kundennutzen."
}
function competitionSentence(market: MarketDataset | null): string {
  if (market && market.competitors.length > 0) {
    return `Gegenüber ${market.competitors[0].name} liegt die Differenzierung in einer belegbaren Lücke: ${market.competitors[0].gap}.`
  }
  return "Gegenüber bestehenden Lösungen wird die konkrete Differenzierung belegt, statt absolute Neuheit zu behaupten."
}
function unionList(list: string[], value: string): string[] {
  return list.includes(value) ? list : [...list, value]
}

export function DraftWorkspace() {
  const [selectedId, setSelectedId] = React.useState(draftFields[0].id)
  const [drafts, setDrafts] = React.useState<Record<string, string>>(() =>
    Object.fromEntries(draftFields.map((f) => [f.id, f.text]))
  )
  const [savedIds, setSavedIds] = React.useState<Set<string>>(
    () => new Set(draftFields.map((f) => f.id))
  )
  const [suggestions, setSuggestions] = React.useState<Record<string, DraftWorkspaceSuggestion>>({})
  const [comments, setComments] = React.useState<Record<string, DraftComment[]>>(() => {
    const out: Record<string, DraftComment[]> = {}
    for (const [k, v] of Object.entries(mockCommentsByField)) out[k] = v.map((c) => ({ ...c }))
    return out
  })
  const [newComment, setNewComment] = React.useState("")
  const [compareOpen, setCompareOpen] = React.useState(false)

  const field = draftFields.find((f) => f.id === selectedId) ?? draftFields[0]
  const text = drafts[field.id] ?? ""
  const dirty = !savedIds.has(field.id)
  const market: MarketDataset | null = isMarketRelevantFieldId(field.id)
    ? mockMarketBySection[field.sectionId] ?? null
    : null
  const suggestion = suggestions[field.id] ?? null
  const fieldComments = comments[field.id] ?? []

  const viewModels: DraftFieldViewModel[] = draftFields.map((f) => {
    const m = isMarketRelevantFieldId(f.id) ? mockMarketBySection[f.sectionId] : undefined
    return {
      id: f.id,
      sectionLabel: sectionLabelFromFieldId(f.id),
      fieldLabel: f.name || "Unbenanntes Feld",
      helperLabel: helperLabel(f.name || ""),
      status: f.status,
      characterLimit: f.charLimit,
      text: drafts[f.id] ?? f.text,
      lastEditedLabel: f.lastEditedLabel,
      evidenceCount: f.evidence.length,
      openIssueCount: f.openPoints.length,
      commentCount: (comments[f.id] ?? []).length,
      hasPlaceholder: hasPlaceholder(drafts[f.id] ?? f.text),
      isMarketRelevant: isMarketRelevantFieldId(f.id),
      marketStatus: m?.status,
      evidenceItems: f.evidence.map((ev) => ({
        id: ev.id,
        claim: ev.claim,
        source: ev.source,
        fundstelle: ev.fundstelle,
        status: ev.status,
      })),
      requirementItems: f.requirements.map((r) => ({ id: r.id, title: r.title, status: r.status })),
      responsible: mockResponsibleByField[f.id],
      reviewer: mockReviewerByField[f.id],
      versions: (mockVersionsByField[f.id] ?? []).map((v) => ({ ...v })),
    }
  })
  const activeVm = viewModels.find((v) => v.id === selectedId) ?? viewModels[0]

  function onChangeText(value: string) {
    setDrafts((prev) => ({ ...prev, [field.id]: value }))
    setSavedIds((prev) => {
      const next = new Set(prev)
      next.delete(field.id)
      return next
    })
  }
  function save() {
    setSavedIds((prev) => new Set(prev).add(field.id))
  }
  function setSuggestion(next: DraftWorkspaceSuggestion) {
    setSuggestions((prev) => ({ ...prev, [field.id]: next }))
  }

  function applyAction(key: string) {
    const base = suggestion?.text ?? text
    const prevImprovements = suggestion?.improvements ?? []
    let newText = base
    let improvement = ""
    let addition = ""
    switch (key) {
      case "create":
        improvement = "klarer formuliert"
        newText = base.trim() || `Entwurf für ${field.name}: ${field.guidance}`
        break
      case "shorten":
        improvement = "auf Zeichenlimit gekürzt"
        newText = field.charLimit ? [...base].slice(0, field.charLimit).join("") : base
        break
      case "innovation":
        improvement = "Innovationsgrad betont"
        addition = "Der Innovationsgrad liegt im neuartigen, gegenüber dem Stand der Technik klar abgegrenzten Ansatz."
        break
      case "practice":
        improvement = "Praxisnutzen stärker"
        addition = "Der konkrete Praxisnutzen ist die messbare Reduktion von Kosten und Ausschuss für Industriekunden."
        break
      case "market":
        improvement = "Marktargument ergänzt"
        addition = marketSentence(market)
        break
      case "competition":
        improvement = "Konkurrenzabgrenzung ergänzt"
        addition = competitionSentence(market)
        break
      case "science":
        improvement = "Wissenschaftliche Fundierung ergänzt"
        addition = "Die Wirksamkeit ist durch Labormessungen und einschlägige Publikationen gestützt."
        break
      default:
        return
    }
    if (addition) newText = appendParagraph(newText, addition)
    setSuggestion({ text: newText, improvements: unionList(prevImprovements, improvement) })
  }

  function applyText(improvement: string, addition: string) {
    const base = suggestion?.text ?? text
    setSuggestion({
      text: appendParagraph(base, addition),
      improvements: unionList(suggestion?.improvements ?? [], improvement),
    })
  }

  function acceptAll() {
    if (suggestion) onChangeText(suggestion.text)
  }
  function acceptParagraph() {
    if (!suggestion) return
    const paragraphs = suggestion.text.split(/\n\s*\n/).map((p) => p.trim()).filter(Boolean)
    const next = paragraphs.find((p) => !text.includes(p))
    if (next) onChangeText(appendParagraph(text, next))
  }
  function discardSuggestion() {
    setSuggestions((prev) => {
      const next = { ...prev }
      delete next[field.id]
      return next
    })
    setCompareOpen(false)
  }

  function addComment() {
    const value = newComment.trim()
    if (!value) return
    const comment: DraftComment = {
      id: `c-${Date.now()}`,
      author: CURRENT_USER,
      timestamp: "gerade eben",
      text: value,
      resolved: false,
    }
    setComments((prev) => ({ ...prev, [field.id]: [...(prev[field.id] ?? []), comment] }))
    setNewComment("")
  }
  function toggleResolved(id: string) {
    setComments((prev) => ({
      ...prev,
      [field.id]: (prev[field.id] ?? []).map((c) => (c.id === id ? { ...c, resolved: !c.resolved } : c)),
    }))
  }

  const kommentareContent = (
    <>
      {fieldComments.length === 0 ? (
        <p className="text-xs text-muted-foreground">Noch keine Kommentare</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {fieldComments.map((c) => (
            <li key={c.id} className="flex flex-col gap-1 rounded-md border border-border px-3 py-2">
              <div className="flex items-center gap-2">
                <Avatar size="sm">
                  <AvatarFallback>{c.author.initials}</AvatarFallback>
                </Avatar>
                <span className="text-xs font-medium text-foreground">{c.author.name}</span>
                <span className="text-[11px] text-muted-foreground">· {c.timestamp}</span>
                <span
                  className={cn(
                    "ml-auto rounded-full px-2 py-0.5 text-[10px] font-medium",
                    c.resolved
                      ? "bg-status-fulfilled/12 text-status-fulfilled"
                      : "bg-status-partial/12 text-status-partial"
                  )}
                >
                  {c.resolved ? "Erledigt" : "Offen"}
                </span>
              </div>
              <p className="text-xs text-foreground">{c.text}</p>
              <button
                type="button"
                onClick={() => toggleResolved(c.id)}
                className="self-start text-[11px] font-medium text-primary hover:underline"
              >
                {c.resolved ? "Wieder öffnen" : "Als erledigt markieren"}
              </button>
            </li>
          ))}
        </ul>
      )}
      <div className="flex flex-col gap-2">
        <Textarea
          value={newComment}
          onChange={(e) => setNewComment(e.target.value)}
          rows={2}
          aria-label="Kommentar hinzufügen"
          placeholder="Kommentar hinzufügen… (@Name zum Erwähnen)"
          className="text-sm"
        />
        <Button size="sm" onClick={addComment} disabled={!newComment.trim()} className="self-start">
          Kommentar hinzufügen
        </Button>
      </div>
    </>
  )

  const defaultTab = pickDefaultTab(activeVm, {
    hasMarketData: !!market,
    hasFindings: false,
    hasBlocker: field.status === "blocked",
  })

  const hasBlocker = draftFields.some((f) => f.status === "blocked")
  const firstOpen =
    draftFields.find((f) => f.status === "blocked") ??
    draftFields.find((f) => f.status === "open" || f.status === "needs_review")

  const footer = (
    <footer className="sticky bottom-0 z-10 border-t border-border bg-background/95 backdrop-blur-sm">
      <div className="mx-auto flex max-w-[1400px] flex-wrap items-center justify-between gap-3 px-6 py-4">
        <p className="text-sm text-muted-foreground">
          {hasBlocker
            ? "Offene Pflichtangaben verhindern die Weitergabe."
            : "Alle Pflichtfelder sind bereit für die Qualitätsprüfung."}
        </p>
        <div className="flex items-center gap-2">
          {hasBlocker && firstOpen && (
            <Button variant="outline" onClick={() => setSelectedId(firstOpen.id)}>
              Zum ersten offenen Punkt
            </Button>
          )}
          {hasBlocker ? (
            <Button disabled>Offene Punkte zuerst klären</Button>
          ) : (
            <Button render={<a href="/review" />} nativeButton={false}>
              Weiter zur Qualitätsprüfung
            </Button>
          )}
        </div>
      </div>
    </footer>
  )

  return (
    <DraftWorkspaceShell
      subtitle="Bearbeiten Sie die Texte pro Innolink-Feld, prüfen Sie KI-Vorschläge, Belege und offene Punkte."
      viewModels={viewModels}
      selectedId={selectedId}
      onSelect={setSelectedId}
      activeVm={activeVm}
      text={text}
      onChangeText={onChangeText}
      onSave={save}
      saveDisabled={!dirty}
      saveStateLabel={dirty ? "Nicht gespeichert" : "Gespeichert"}
      marketHeaderLabel={market ? HEADER_MARKET_LABEL[market.status] : undefined}
      aiActions={AI_GOALS}
      aiEnabled
      onAiAction={applyAction}
      suggestion={suggestion}
      onAcceptAll={acceptAll}
      onAcceptParagraph={acceptParagraph}
      onToggleCompare={() => setCompareOpen((v) => !v)}
      compareOpen={compareOpen}
      onDiscard={discardSuggestion}
      assistant={
        <AssistantPanel
          key={selectedId}
          vm={activeVm}
          defaultTab={defaultTab}
          market={{ data: market, relevant: isMarketRelevantFieldId(field.id), live: false, onApply: applyText }}
          suggestionExists={!!suggestion}
          kommentareContent={kommentareContent}
        />
      }
      footer={footer}
    />
  )
}
