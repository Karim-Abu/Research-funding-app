"use client"

import * as React from "react"
import { ExternalLink, Globe, Loader2, ShieldAlert } from "lucide-react"

import { QueryApprovalList, approvedIds, type ApprovalQuery } from "@/components/research/query-approval-list"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { flatToPrivacyClass, isExternalBlocked } from "@/lib/data-class"
import { type QueryCandidateDto } from "@/lib/market-research"
import {
  RESEARCH_MODULE_LABELS,
  approveResearchBrief,
  getResearchWorkspace,
  planResearchQueries,
  previewBriefQuery,
  runResearchBrief,
  saveResearchBrief,
  suggestResearchBrief,
  type ResearchBriefDto,
  type ResearchBriefInput,
  type ResearchModule,
  type ResearchQueryDto,
  type ResearchWorkspaceDto,
} from "@/lib/research-brief"
import { discardResearchResult, importResearchResult } from "@/lib/research"
import type { DataClass } from "@/lib/types"

const MODULES = Object.keys(RESEARCH_MODULE_LABELS) as ResearchModule[]

function formOf(brief: ResearchBriefDto): ResearchBriefInput {
  return {
    application_domain: brief.application_domain,
    technology_class: brief.technology_class,
    target_customer_segments: [...brief.target_customer_segments],
    region: brief.region,
    competence_needs: [...brief.competence_needs],
    modules: [...brief.modules],
  }
}

function approvalsOf(rows: ResearchQueryDto[]): ApprovalQuery[] {
  return rows.map((row) => ({
    query_text: row.query_text,
    purpose: row.planner_purpose,
    public_safe: row.firewall_decision !== "block",
    approval_required: true,
    approval_id: row.approval_id,
    decision: row.status,
    firewall_decision: row.firewall_decision,
    risk_label: row.risk_label,
    redaction_summary: row.redaction_summary,
  }))
}

export function PublicResearchPanel({
  projectId,
  dataClass = "public",
  onImported,
}: {
  projectId: string
  dataClass?: DataClass
  onImported?: () => void
}) {
  const blocked = isExternalBlocked(flatToPrivacyClass(dataClass))
  const [workspace, setWorkspace] = React.useState<ResearchWorkspaceDto | null>(null)
  const [form, setForm] = React.useState<ResearchBriefInput | null>(null)
  const [queries, setQueries] = React.useState<ApprovalQuery[]>([])
  const [activeModule, setActiveModule] = React.useState<ResearchModule>("market_growth")
  const [editingApproved, setEditingApproved] = React.useState(false)
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  const refresh = React.useCallback(async () => {
    const next = await getResearchWorkspace(projectId)
    setWorkspace(next)
    if (next.brief.latest) setForm(formOf(next.brief.latest))
    setQueries(approvalsOf(next.queries))
  }, [projectId])

  React.useEffect(() => {
    if (!blocked) void refresh().catch(() => setError("Der Recherchestatus konnte nicht geladen werden."))
  }, [blocked, refresh])

  const act = async (operation: () => Promise<unknown>) => {
    setBusy(true)
    setError(null)
    try {
      await operation()
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Die Rechercheaktion ist fehlgeschlagen.")
    } finally {
      setBusy(false)
    }
  }

  if (blocked) {
    return (
      <section className="rounded-lg border border-border bg-card p-5" data-testid="public-research-panel">
        <div className="flex items-center gap-2"><ShieldAlert className="size-4" /><h3 className="font-semibold">Öffentliche Recherche</h3></div>
        <p className="mt-1 text-xs text-muted-foreground">Für NDA-geschützte oder unklare Datenklassen werden keine externen Dienste aufgerufen.</p>
      </section>
    )
  }

  const brief = workspace?.brief.latest ?? null
  const approved = workspace?.brief.active_approved ?? null
  const queryRows = workspace?.queries ?? []
  const visibleQueryIndexes = queryRows
    .map((row, index) => ({ row, index }))
    .filter(({ row }) => (
      row.module === activeModule
      && row.research_brief_id === approved?.research_brief_id
    ))
  const visibleQueries = visibleQueryIndexes.map(({ index }) => queries[index]).filter(Boolean)
  const historicalQueries = queryRows
    .map((row, index) => ({ row, query: queries[index] }))
    .filter(({ row, query }) => (
      Boolean(query)
      && row.module === activeModule
      && row.research_brief_id !== approved?.research_brief_id
    ))
    .map(({ query }) => query)
  const visibleResults = (workspace?.results ?? []).filter((row) => row.module === activeModule)
  const demo = workspace?.provider_mode === "fake_demo"
  const briefFieldsDisabled = brief?.status === "approved" && !editingApproved

  return (
    <section className="rounded-lg border border-border bg-card p-5" data-testid="public-research-panel">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <div className="flex items-center gap-2"><Globe className="size-4" /><h3 className="font-semibold">Öffentliche Recherche</h3></div>
          <p className="mt-1 text-xs text-muted-foreground">Queries entstehen nur aus dem geprüften öffentlichen Recherchebrief.</p>
          <p className="mt-1 text-xs text-muted-foreground">Keine Rohprojektidee, Partnernamen, Budgets oder Kontaktangaben eintragen.</p>
        </div>
        {workspace && <Badge variant="outline">{workspace.provider_mode === "live" ? "Live-Recherche" : workspace.provider_mode === "fake_demo" ? "Demo-Recherche" : "Nicht verfügbar"}</Badge>}
      </div>

      {demo && <p className="mt-3 rounded border border-amber-300 bg-amber-50 p-2 text-xs text-amber-900" data-testid="research-demo-banner">Demo-Recherche – keine echten Webquellen. Ergebnisse können nicht übernommen werden.</p>}
      {error && <p role="alert" className="mt-3 text-sm text-destructive">{error}</p>}

      {!brief && (
        <Button className="mt-4" variant="outline" disabled={busy} onClick={() => void act(() => suggestResearchBrief(projectId))}>
          {busy && <Loader2 className="size-4 animate-spin" />} Recherchebrief vorschlagen
        </Button>
      )}

      {brief && form && (
        <div className="mt-4 space-y-3" data-testid="research-brief-form">
          <div className="grid gap-3 md:grid-cols-2">
            <BriefField label="Anwendungsdomäne" value={form.application_domain} onChange={(value) => setForm({ ...form, application_domain: value })} disabled={briefFieldsDisabled} />
            <BriefField label="Technologieklasse" value={form.technology_class} onChange={(value) => setForm({ ...form, technology_class: value })} disabled={briefFieldsDisabled} />
            <BriefField label="Zielkundensegmente (kommagetrennt)" value={form.target_customer_segments.join(", ")} onChange={(value) => setForm({ ...form, target_customer_segments: split(value) })} disabled={briefFieldsDisabled} />
            <BriefField label="Region" value={form.region} onChange={(value) => setForm({ ...form, region: value })} disabled={briefFieldsDisabled} />
            <BriefField label="Gesuchte Forschungs-/Partnerkompetenzen (kommagetrennt)" value={form.competence_needs.join(", ")} onChange={(value) => setForm({ ...form, competence_needs: split(value) })} disabled={briefFieldsDisabled} />
          </div>
          <fieldset disabled={briefFieldsDisabled}>
            <legend className="text-xs font-medium">Recherchemodule</legend>
            <div className="mt-1 flex flex-wrap gap-2">
              {MODULES.map((module) => <label key={module} className="flex items-center gap-1 rounded border px-2 py-1 text-xs"><input type="checkbox" checked={form.modules.includes(module)} onChange={(event) => setForm({ ...form, modules: event.target.checked ? [...form.modules, module] : form.modules.filter((item) => item !== module) })} />{RESEARCH_MODULE_LABELS[module]}</label>)}
            </div>
          </fieldset>
          <div className="flex flex-wrap gap-2">
            {brief.status === "draft" ? <>
              <Button variant="outline" disabled={busy} onClick={() => void act(() => saveResearchBrief(projectId, form))}>Entwurf speichern</Button>
              <Button disabled={busy} onClick={() => void act(async () => { const saved = await saveResearchBrief(projectId, form); await approveResearchBrief(saved.research_brief_id) })}>Public-safe Brief freigeben</Button>
            </> : editingApproved ? <>
              <Button variant="outline" disabled={busy} onClick={() => { setForm(formOf(brief)); setEditingApproved(false) }}>Abbrechen</Button>
              <Button disabled={busy} onClick={() => void act(async () => { await saveResearchBrief(projectId, form); setEditingApproved(false) })}>Neue Briefversion speichern</Button>
            </> : <>
              <Badge>Brief v{brief.version} freigegeben</Badge>
              <Button variant="outline" disabled={busy} onClick={() => setEditingApproved(true)}>Brief ändern</Button>
              <Button variant="outline" disabled={busy || queryRows.some((row) => row.research_brief_id === brief.research_brief_id)} onClick={() => void act(() => planResearchQueries(brief.research_brief_id))}>Queries erzeugen</Button>
            </>}
          </div>
        </div>
      )}

      {approved && (
        <div className="mt-5">
          <div className="flex gap-1 overflow-x-auto pb-2" aria-label="Recherchemodule">
            {approved.modules.map((module) => <Button key={module} size="xs" variant={activeModule === module ? "default" : "outline"} onClick={() => setActiveModule(module)}>{RESEARCH_MODULE_LABELS[module]}</Button>)}
          </div>

          {visibleQueries.length > 0 && <div className="mt-3">
            <QueryApprovalList
              projectId={projectId}
              queries={visibleQueries}
              onChange={(next) => setQueries((all) => { const copy = [...all]; visibleQueryIndexes.forEach(({ index }, offset) => { copy[index] = next[offset] }); return copy })}
              onPreview={async (query, editedText): Promise<QueryCandidateDto> => {
                const original = queryRows.find((row) => row.approval_id === query.approval_id)
                if (!original) throw new Error("Query-Provenienz fehlt.")
                const next = await previewBriefQuery(approved.research_brief_id, { ...original, query_text: editedText })
                return { query_text: next.query_text, purpose: next.planner_purpose, public_safe: next.firewall_decision !== "block", approval_required: true, approval_id: next.approval_id }
              }}
            />
            <Button className="mt-2" disabled={busy || approvedIds(visibleQueries).length === 0} onClick={() => void act(() => runResearchBrief(approved.research_brief_id, approvedIds(visibleQueries)))}>Freigegebene Queries ausführen</Button>
          </div>}

          {historicalQueries.length > 0 && <details className="mt-3 rounded border p-2 text-xs">
            <summary className="cursor-pointer font-medium">Frühere Query-Stände</summary>
            <div className="mt-2"><QueryApprovalList projectId={projectId} queries={historicalQueries} onChange={() => undefined} /></div>
          </details>}

          <div className="mt-4 space-y-3" data-testid="research-results">
            {visibleResults.length === 0 && <p className="text-sm text-muted-foreground">Noch keine Resultate für dieses Modul.</p>}
            {visibleResults.map((result) => <article key={result.result_id} className="rounded border p-3">
              <div className="flex items-start justify-between gap-2"><div className="min-w-0"><h4 className="font-medium">{result.title}</h4><a href={result.final_url ?? result.source_url} target="_blank" rel="noreferrer" className="break-all text-xs text-primary hover:underline">{result.final_url ?? result.source_url}</a><p className="text-xs text-muted-foreground">{result.domain} · abgerufen {new Date(result.retrieved_at).toLocaleDateString("de-CH")}</p></div><Badge variant="outline">{result.execution_mode === "fake_demo" ? "Demo" : result.status === "imported" ? "Übernommen" : result.status === "rejected" ? "Verworfen" : "Quellenkandidat – fachlich prüfen"}</Badge></div>
              {result.snippet && <p className="mt-2 text-sm">{result.snippet}</p>}
              <p className="mt-2 text-xs text-muted-foreground">{result.relevance_reason}</p>
              {result.partner_candidate && <dl className="mt-2 grid gap-1 rounded bg-muted p-2 text-xs">
                <div><dt className="font-medium">Organisation/Forschungsgruppe</dt><dd>{result.partner_candidate.organization_or_group}</dd></div>
                <div><dt className="font-medium">Standort</dt><dd>{result.partner_candidate.location ?? "unbestätigt"}</dd></div>
                <div><dt className="font-medium">Gesuchte Kompetenz</dt><dd>{result.partner_candidate.expertise_keywords.join(", ") || "nicht angegeben"}</dd></div>
                <div><dt className="font-medium">Mögliche Projektrolle</dt><dd>{result.partner_candidate.possible_project_role}</dd></div>
                <div><dt className="font-medium">Warum potenziell passend</dt><dd>{result.partner_candidate.why_potentially_relevant}</dd></div>
                <div><dt className="font-medium">Status</dt><dd>Kandidat – keine Förderberechtigung bestätigt. Keine Kontaktaufnahme.</dd></div>
              </dl>}
              {result.source_locations.map((location, index) => <details key={`${location.source_version_id}-${index}`} className="mt-2 text-xs"><summary className="cursor-pointer font-medium">Fundstelle aus abgerufener Seite</summary><p className="mt-1 whitespace-pre-wrap rounded bg-muted p-2">{location.excerpt}</p><p className="text-muted-foreground">Fundstelle exakt abgerufen – fachliche Stützung nicht bestätigt.</p></details>)}
              <div className="mt-3 flex gap-2"><Button size="xs" variant="outline" onClick={() => window.open(result.final_url ?? result.source_url, "_blank", "noopener,noreferrer")}><ExternalLink className="size-3" /> Öffnen</Button>{result.status === "candidate" && result.execution_mode !== "fake_demo" && <Button size="xs" onClick={() => void act(async () => { await importResearchResult(result.result_id); onImported?.() })}>Übernehmen</Button>}{result.status === "candidate" && <Button size="xs" variant="ghost" onClick={() => void act(() => discardResearchResult(result.result_id))}>Verwerfen</Button>}</div>
            </article>)}
          </div>
        </div>
      )}
    </section>
  )
}

function split(value: string): string[] {
  return value.split(",").map((item) => item.trim()).filter(Boolean)
}

function BriefField({ label, value, onChange, disabled }: { label: string; value: string; onChange: (value: string) => void; disabled: boolean }) {
  const id = React.useId()
  return <div><Label htmlFor={id}>{label}</Label><Input id={id} value={value} disabled={disabled} onChange={(event) => onChange(event.target.value)} /></div>
}
