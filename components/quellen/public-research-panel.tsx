"use client"

import * as React from "react"
import { ExternalLink, Globe, Loader2, ShieldAlert } from "lucide-react"

import { QueryApprovalList, approvedIds, type ApprovalQuery } from "@/components/research/query-approval-list"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { flatToPrivacyClass, isExternalBlocked } from "@/lib/data-class"
import { type QueryCandidateDto } from "@/lib/market-research"
import {
  RESEARCH_MODULE_LABELS,
  approveResearchBrief,
  getResearchWorkspace,
  planResearchQueries,
  previewBriefQuery,
  reviewResearchResult,
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
import { createUrlSource } from "@/lib/sources"
import type { DataClassification } from "@/lib/data-classification"
import type { DataClass } from "@/lib/types"

const MODULES: ResearchModule[] = [
  "market_growth",
  "competition_alternatives",
  "state_of_the_art",
  "swiss_research_partners",
]
const PUBLIC_SOURCE_CLASSIFICATION: DataClassification = {
  sensitivity: "public",
  origin: "public_source",
  processing_mode: "deterministic_only",
  web_research_mode: "validated_public",
  nda_applies: false,
}
const FIELD_EXAMPLES = {
  application_domain: "Schweizer Gesundheitsdatenaustausch",
  technology_class: "dezentrale Zugriffssteuerung / Audit Trail / DLT",
  target_customer_segments: "medizinische Labore, Arztpraxen, Spitäler, Health-IT-Anbieter",
  region: "Schweiz / DACH",
  competence_needs: "Healthcare Cybersecurity, Interoperabilität, Distributed Systems, Data Governance",
} as const
const GENERIC_CUSTOMER_WORDS = new Set([
  "unternehmer", "unternehmen", "kunde", "kunden", "kundschaft", "kmu",
  "organisation", "organisationen", "nutzer", "anwender",
])
const REGION_WORDS = new Set([
  "schweiz", "schweizer", "schweizerisch", "schweizerische",
  "schweizerischer", "schweizerischen", "swiss",
])
const GENERIC_COMPETENCE_WORDS = new Set([
  "eth", "epfl", "universität", "universitaet", "hochschule", "fachhochschule",
  "institut", "kompetenzzentrum", "competence", "center", "centre",
])

type BriefFieldKey =
  | "application_domain"
  | "technology_class"
  | "target_customer_segments"
  | "competence_needs"
type BriefFieldErrors = Partial<Record<BriefFieldKey, string>>

function formOf(brief: ResearchBriefDto): ResearchBriefInput {
  return {
    application_domain: brief.application_domain,
    technology_class: brief.technology_class,
    target_customer_segments: [...brief.target_customer_segments],
    region: brief.region,
    competence_needs: [...brief.competence_needs],
    modules: brief.modules.filter((module) => MODULES.includes(module)),
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
    risk_score: row.risk_score ?? 0,
    redaction_summary: row.redaction_summary,
  }))
}

function words(value: string): string[] {
  return value.toLocaleLowerCase("de-CH").match(/[\p{L}\p{N}]+/gu) ?? []
}

function comparisonKey(value: string): string {
  return words(value).join("")
}

function genericCustomer(value: string): boolean {
  const meaningful = words(value).filter((word) => !REGION_WORDS.has(word))
  return meaningful.length === 0 || meaningful.every((word) => GENERIC_CUSTOMER_WORDS.has(word))
}

function concreteCompetence(value: string): boolean {
  const trimmed = value.trim()
  if (!trimmed || /^[A-ZÄÖÜ0-9]{2,10}$/.test(trimmed)) return false
  const meaningful = words(trimmed)
  return meaningful.length > 0 && !meaningful.every((word) => GENERIC_COMPETENCE_WORDS.has(word))
}

function approvalErrors(form: ResearchBriefInput): BriefFieldErrors {
  const errors: BriefFieldErrors = {}
  if (!form.application_domain.trim()) {
    errors.application_domain = "Bitte einen konkreten Anwendungsbereich angeben."
  }
  if (!form.technology_class.trim()) {
    errors.technology_class = "Bitte eine Technologieklasse oder ein technisches Prinzip angeben."
  }
  if (
    form.application_domain.trim()
    && form.technology_class.trim()
    && comparisonKey(form.application_domain) === comparisonKey(form.technology_class)
  ) {
    const message = "Anwendungsdomäne und Technologieklasse müssen unterschiedlich sein."
    errors.application_domain = message
    errors.technology_class = message
  }
  const hasMarketModule = form.modules.some((module) =>
    module === "market_growth" || module === "competition_alternatives"
  )
  if (
    hasMarketModule
    && (
      form.target_customer_segments.length === 0
      || form.target_customer_segments.every(genericCustomer)
    )
  ) {
    errors.target_customer_segments =
      "Bitte mindestens ein konkretes Kundensegment statt nur Kunden, KMU oder Unternehmen angeben."
  }
  if (
    form.modules.includes("swiss_research_partners")
    && (
      form.competence_needs.length === 0
      || !form.competence_needs.some(concreteCompetence)
    )
  ) {
    errors.competence_needs =
      "Bitte mindestens eine konkrete Fachkompetenz statt nur eines Organisationsnamens angeben."
  }
  return errors
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
  const [fieldErrors, setFieldErrors] = React.useState<BriefFieldErrors>({})
  const [manualUrl, setManualUrl] = React.useState("")
  const [manualTitle, setManualTitle] = React.useState("")
  const [manualContent, setManualContent] = React.useState("")

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

  const approveBrief = () => {
    if (!form) return
    const nextErrors = approvalErrors(form)
    setFieldErrors(nextErrors)
    if (Object.keys(nextErrors).length > 0) return
    void act(async () => {
      const saved = await saveResearchBrief(projectId, form)
      await approveResearchBrief(saved.research_brief_id)
    })
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
          <p className="mt-1 text-xs text-muted-foreground">Vorschläge bestätigen keine fachliche Richtigkeit. Bitte alle Felder vor der Freigabe prüfen.</p>
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
          <h4 className="text-sm font-semibold">Was soll öffentlich recherchiert werden?</h4>
          <div className="grid gap-3 md:grid-cols-2">
            <BriefField label="Anwendungsdomäne" value={form.application_domain} onChange={(value) => { setForm({ ...form, application_domain: value }); setFieldErrors((current) => ({ ...current, application_domain: undefined })) }} disabled={briefFieldsDisabled} example={FIELD_EXAMPLES.application_domain} help={!form.application_domain.trim() ? "In welchem konkreten Anwendungsbereich soll recherchiert werden?" : undefined} error={fieldErrors.application_domain} />
            <BriefField label="Technologieklasse" value={form.technology_class} onChange={(value) => { setForm({ ...form, technology_class: value }); setFieldErrors((current) => ({ ...current, technology_class: undefined })) }} disabled={briefFieldsDisabled} example={FIELD_EXAMPLES.technology_class} help={!form.technology_class.trim() ? "Welche Technologieklasse oder welches technische Prinzip soll verglichen werden?" : undefined} error={fieldErrors.technology_class} />
            <BriefField label="Zielkundensegmente (kommagetrennt)" value={form.target_customer_segments.join(", ")} onChange={(value) => { setForm({ ...form, target_customer_segments: split(value) }); setFieldErrors((current) => ({ ...current, target_customer_segments: undefined })) }} disabled={briefFieldsDisabled} example={FIELD_EXAMPLES.target_customer_segments} help={form.target_customer_segments.length === 0 ? "Welche konkreten Organisationstypen entscheiden, nutzen oder bezahlen?" : undefined} error={fieldErrors.target_customer_segments} />
            <BriefField label="Region" value={form.region} onChange={(value) => setForm({ ...form, region: value })} disabled={briefFieldsDisabled} example={FIELD_EXAMPLES.region} />
            <BriefField label="Gesuchte Forschungs-/Partnerkompetenzen (kommagetrennt)" value={form.competence_needs.join(", ")} onChange={(value) => { setForm({ ...form, competence_needs: split(value) }); setFieldErrors((current) => ({ ...current, competence_needs: undefined })) }} disabled={briefFieldsDisabled} example={FIELD_EXAMPLES.competence_needs} help={form.competence_needs.length === 0 ? "Welche konkrete fachliche Kompetenz fehlt für die Partnersuche?" : undefined} error={fieldErrors.competence_needs} />
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
              <Button disabled={busy} onClick={approveBrief}>Public-safe Brief freigeben</Button>
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
            {approved.modules.filter((module) => MODULES.includes(module)).map((module) => <Button key={module} size="xs" variant={activeModule === module ? "default" : "outline"} onClick={() => setActiveModule(module)}>{RESEARCH_MODULE_LABELS[module]}</Button>)}
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
                return {
                  query_text: next.query_text,
                  purpose: next.planner_purpose,
                  public_safe: next.firewall_decision !== "block",
                  approval_required: true,
                  approval_id: next.approval_id ?? undefined,
                  blocked_reason: next.firewall_decision === "block" ? "query_blocked" : undefined,
                  firewall_decision: next.firewall_decision,
                  risk_label: next.risk_label,
                  risk_score: next.risk_score,
                  redaction_summary: next.redaction_summary,
                } as ApprovalQuery
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
              <div className="flex items-start justify-between gap-2"><div className="min-w-0"><h4 className="font-medium">{result.title}</h4><a href={result.final_url ?? result.source_url} target="_blank" rel="noreferrer" className="break-all text-xs text-primary hover:underline">{result.final_url ?? result.source_url}</a><p className="text-xs text-muted-foreground">{result.publisher ?? result.domain} · {result.published_at ? new Date(result.published_at).toLocaleDateString("de-CH") : "Datum nicht verfügbar"} · Aktualität: {result.freshness_label ?? "unbekannt"}</p></div><Badge variant="outline">{result.execution_mode === "fake_demo" ? "Demo" : result.status === "imported" && result.content_review_status === "reviewed" ? "Inhaltlich geprüft" : result.status === "imported" ? "Übernommen" : result.status === "rejected" ? "Verworfen" : "Kandidat"}</Badge></div>
              {result.snippet && <p className="mt-2 text-sm">{result.snippet}</p>}
              <p className="mt-2 text-xs text-muted-foreground">{result.relevance_reason}</p>
              <dl className="mt-2 grid gap-1 text-xs sm:grid-cols-2">
                <div><dt className="font-medium">Potentieller Abschnitt</dt><dd>{(result.potential_sections ?? []).join(", ") || "noch offen"}</dd></div>
                <div><dt className="font-medium">Vorläufige Quellenqualität</dt><dd>{(result.source_quality ?? "unbewertet").replaceAll("_", " ")}</dd></div>
                <div><dt className="font-medium">Fundstellenabdeckung</dt><dd>{!result.coverage_status || result.coverage_status === "not_checked" ? "nicht geprüft" : result.coverage_status}</dd></div>
                <div><dt className="font-medium">Inhaltliche Stützung</dt><dd>{supportLabel(result.support_status ?? "not_checked")}</dd></div>
              </dl>
              {result.partner_candidate && <dl className="mt-2 grid gap-1 rounded bg-muted p-2 text-xs">
                <div><dt className="font-medium">Organisation/Forschungsgruppe</dt><dd>{result.partner_candidate.organization_or_group}</dd></div>
                <div><dt className="font-medium">Standort</dt><dd>{result.partner_candidate.location ?? "unbestätigt"}</dd></div>
                <div><dt className="font-medium">Gesuchte Kompetenz</dt><dd>{result.partner_candidate.expertise_keywords.join(", ") || "nicht angegeben"}</dd></div>
                <div><dt className="font-medium">Mögliche Projektrolle</dt><dd>{result.partner_candidate.possible_project_role}</dd></div>
                <div><dt className="font-medium">Warum potenziell passend</dt><dd>{result.partner_candidate.why_potentially_relevant}</dd></div>
                <div><dt className="font-medium">Eligibility-Referenz</dt><dd>{eligibilityLabel(result.partner_candidate.status)}{result.partner_candidate.eligibility_reference_date ? ` (Stand ${result.partner_candidate.eligibility_reference_date})` : ""}</dd></div>
                <div><dt className="font-medium">Kompetenzlücke</dt><dd>{result.partner_candidate.competence_gap ?? "menschlich zu konkretisieren"}</dd></div>
                <div><dt className="font-medium">Track Record</dt><dd>{(result.partner_candidate.track_record_links ?? []).length ? (result.partner_candidate.track_record_links ?? []).map((link) => <a key={link} href={link} target="_blank" rel="noreferrer" className="block break-all text-primary hover:underline">{link}</a>) : "noch nicht separat belegt"}</dd></div>
                <div><dt className="font-medium">Grenze</dt><dd>Keine Aussage zu Verfügbarkeit oder Interesse. Endgültige Beitragsberechtigung menschlich prüfen.</dd></div>
              </dl>}
              {result.source_locations.map((location, index) => <details key={`${location.source_version_id}-${index}`} className="mt-2 text-xs"><summary className="cursor-pointer font-medium">Fundstelle aus abgerufener Seite</summary><p className="mt-1 whitespace-pre-wrap rounded bg-muted p-2">{location.excerpt}</p><p className="text-muted-foreground">Fundstelle exakt abgerufen – fachliche Stützung nicht bestätigt.</p></details>)}
              <div className="mt-3 flex flex-wrap gap-2"><Button size="xs" variant="outline" onClick={() => window.open(result.final_url ?? result.source_url, "_blank", "noopener,noreferrer")}><ExternalLink className="size-3" /> Öffnen</Button>{result.status === "candidate" && result.execution_mode !== "fake_demo" && <Button size="xs" onClick={() => void act(async () => { await importResearchResult(result.result_id); onImported?.() })}>Übernehmen und prüfen</Button>}{result.status === "candidate" && <Button size="xs" variant="ghost" onClick={() => void act(() => discardResearchResult(result.result_id))}>Verwerfen</Button>}{result.status === "imported" && <><Button size="xs" variant="outline" onClick={() => void act(() => reviewResearchResult(result.result_id, "supports"))}>Stützt</Button><Button size="xs" variant="outline" onClick={() => void act(() => reviewResearchResult(result.result_id, "partially_supports"))}>Teilweise</Button><Button size="xs" variant="ghost" onClick={() => void act(() => reviewResearchResult(result.result_id, "does_not_support"))}>Stützt nicht</Button></>}</div>
              <details className="mt-2 text-xs text-muted-foreground"><summary className="cursor-pointer">Technische Details</summary><p>Ausführungsmodus: {result.execution_mode ?? "unbekannt"} · Task-ID: {result.task_id}</p></details>
            </article>)}
          </div>

          {(workspace?.provider_mode === "unavailable" || error) && <div className="mt-4 rounded border p-3" data-testid="manual-research-fallback">
            <h4 className="text-sm font-medium">Manueller Quellenimport</h4>
            <p className="mt-1 text-xs text-muted-foreground">Bei Netz- oder Recherchedienstfehlern: öffentliche URL und selbst kopierten Seiteninhalt einfügen. Der Server ruft die URL nicht ab. Alternativ steht der bestehende PDF-Upload auf dieser Seite zur Verfügung.</p>
            <div className="mt-2 grid gap-2 md:grid-cols-2"><BriefField label="Öffentliche HTTPS-URL" value={manualUrl} onChange={setManualUrl} disabled={busy} /><BriefField label="Titel" value={manualTitle} onChange={setManualTitle} disabled={busy} /></div>
            <Label className="mt-2 block" htmlFor="manual-research-content">Kopierter Seiteninhalt</Label>
            <Textarea id="manual-research-content" value={manualContent} disabled={busy} onChange={(event) => setManualContent(event.target.value)} rows={6} />
            <Button className="mt-2" size="sm" variant="outline" disabled={busy || !manualUrl.trim() || !manualContent.trim()} onClick={() => void act(async () => { await createUrlSource(projectId, manualUrl, manualTitle || null, PUBLIC_SOURCE_CLASSIFICATION, manualContent); setManualUrl(""); setManualTitle(""); setManualContent(""); onImported?.() })}>Manuell als Quelle übernehmen</Button>
          </div>}
        </div>
      )}
    </section>
  )
}

function supportLabel(value: string): string {
  return ({ not_checked: "nicht geprüft", supports: "stützt", partially_supports: "stützt teilweise", does_not_support: "stützt nicht" } as Record<string, string>)[value] ?? value
}

function eligibilityLabel(value: string): string {
  return ({ eligibility_verified: "Institution und Domain in lokaler Innosuisse-Referenz verifiziert", likely_eligible: "Gruppe unter gelisteter Mutterinstitution – wahrscheinlich berechtigt", needs_human_check: "Kein belastbarer Nachweis – menschlich prüfen", candidate_not_eligibility_confirmed: "Kein belastbarer Nachweis – menschlich prüfen" } as Record<string, string>)[value] ?? "Kein belastbarer Nachweis – menschlich prüfen"
}

function split(value: string): string[] {
  return value.split(",").map((item) => item.trim()).filter(Boolean)
}

function BriefField({
  label,
  value,
  onChange,
  disabled,
  example,
  help,
  error,
}: {
  label: string
  value: string
  onChange: (value: string) => void
  disabled: boolean
  example?: string
  help?: string
  error?: string
}) {
  const id = React.useId()
  const descriptionId = `${id}-description`
  return <div>
    <Label htmlFor={id}>{label}</Label>
    <Input id={id} value={value} disabled={disabled} aria-invalid={Boolean(error)} aria-describedby={(example || help || error) ? descriptionId : undefined} onChange={(event) => onChange(event.target.value)} />
    {(example || help || error) && <div id={descriptionId} className="mt-1 space-y-0.5 text-xs">
      {example && <p className="text-muted-foreground">Beispiel: {example}</p>}
      {help && <p className="text-primary">{help}</p>}
      {error && <p role="alert" className="text-destructive">{error}</p>}
    </div>}
  </div>
}
