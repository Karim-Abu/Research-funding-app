"use client"

import * as React from "react"
import { Loader2, RefreshCw, Save } from "lucide-react"
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  getBudgetPrecheck,
  getProject,
  patchProject,
  type BudgetPrecheckCheckDto,
  type BudgetPrecheckDto,
  type BudgetPrecheckStatus,
  type ProjectBudgetPatch,
  type ProjectDto,
} from "@/lib/projects"
import type { StructuredImportSummaryDto } from "@/lib/imports"

// Budgeteckwerte: Erfassung + read-only «Formale Vorprüfung». Gerechnet wird
// ausschliesslich im Backend-Rule-Kern (gleiche Handler und Registry-Schwellen
// wie der Analyse-Lauf) — das Frontend zeigt nur an.

// Eigenes Vorprüfungs-Vokabular — bewusst KEIN Requirement-/Evidenz-Status.
const PRECHECK_BADGE: Record<
  BudgetPrecheckStatus,
  { label: string; className: string }
> = {
  fulfilled: {
    label: "Erfüllt",
    className: "border-status-fulfilled/60 text-status-fulfilled",
  },
  review: {
    label: "Prüfen",
    className: "border-status-partial/60 text-status-partial",
  },
  blocker: { label: "Blocker", className: "border-destructive/60 text-destructive" },
  missing: { label: "Angabe fehlt", className: "text-muted-foreground" },
}

const NUMBER_FORMAT = new Intl.NumberFormat("de-CH", {
  maximumFractionDigits: 2,
})

function chf(value: number | null): string {
  return value === null ? "Angabe fehlt" : NUMBER_FORMAT.format(value)
}

/** Schwellen-Erklärung aus der Registry-Condition — nichts wird hier
 *  nachgerechnet oder zweitkodiert. */
function conditionSentence(check: BudgetPrecheckCheckDto): string {
  const min = check.condition.min
  const max = check.condition.max
  if (check.condition.type === "range_percent") {
    return `Der Beitrag der Umsetzungspartner (Eigenleistung + Barbeitrag) muss ${String(min)}–${String(max)} % der direkten Projektkosten betragen.`
  }
  if (check.condition.type === "min_percent") {
    return `Der Barbeitrag muss mindestens ${String(min)} % der direkten Projektkosten betragen.`
  }
  return check.reason
}

interface BudgetFormState {
  direct_total_project_costs_excluding_overhead: string
  implementation_own_contribution: string
  cash_contribution: string
  total_requested_funding: string
  total_requested_funding_including_overhead: string
  budget_exception_basis: string
  duration_months: string
}

const EMPTY: BudgetFormState = {
  direct_total_project_costs_excluding_overhead: "",
  implementation_own_contribution: "",
  cash_contribution: "",
  total_requested_funding: "",
  total_requested_funding_including_overhead: "",
  budget_exception_basis: "",
  duration_months: "",
}

const AMOUNT_FIELDS: Array<{
  key: keyof Pick<
    BudgetFormState,
    | "direct_total_project_costs_excluding_overhead"
    | "implementation_own_contribution"
    | "cash_contribution"
    | "total_requested_funding"
    | "total_requested_funding_including_overhead"
  >
  label: string
}> = [
  {
    key: "direct_total_project_costs_excluding_overhead",
    label: "Direkte Projektkosten (ohne Overhead)",
  },
  {
    key: "implementation_own_contribution",
    label: "Eigenleistung Umsetzungspartner",
  },
  { key: "cash_contribution", label: "Barbeitrag (Cash)" },
  { key: "total_requested_funding", label: "Beantragte Fördersumme" },
  {
    key: "total_requested_funding_including_overhead",
    label: "Beantragte Fördersumme inkl. Overhead (nur Information)",
  },
]

function toFormValue(value: number | string | null | undefined): string {
  return value === null || value === undefined ? "" : String(value)
}

/** "" → null; sonst Zahl (Komma erlaubt). Nie Number("") === 0. */
function parseAmount(raw: string): number | null | "invalid" {
  const trimmed = raw.trim()
  if (trimmed === "") return null
  const value = Number(trimmed.replace(",", "."))
  if (!Number.isFinite(value) || value < 0) return "invalid"
  return value
}

function parseDuration(raw: string): number | null | "invalid" {
  const trimmed = raw.trim()
  if (trimmed === "") return null
  const value = Number(trimmed)
  if (!Number.isInteger(value) || value < 1) return "invalid"
  return value
}

export function BudgetForm({
  projectId,
  importSummary,
}: {
  projectId: string
  importSummary?: StructuredImportSummaryDto | null
}) {
  const [form, setForm] = React.useState<BudgetFormState>(EMPTY)
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const [saved, setSaved] = React.useState(false)
  const [loadError, setLoadError] = React.useState(false)
  const [precheck, setPrecheck] = React.useState<BudgetPrecheckDto | null>(null)
  const [precheckUnavailable, setPrecheckUnavailable] = React.useState(false)

  const loadPrecheck = React.useCallback(async () => {
    try {
      setPrecheck(await getBudgetPrecheck(projectId))
      setPrecheckUnavailable(false)
    } catch {
      // Die Erfassung bleibt voll nutzbar — nur die Anzeige fehlt.
      setPrecheckUnavailable(true)
    }
  }, [projectId])

  React.useEffect(() => {
    void loadPrecheck()
  }, [loadPrecheck])

  const loadProject = React.useCallback(async () => {
    try {
      const project: ProjectDto = await getProject(projectId)
      setForm({
        direct_total_project_costs_excluding_overhead: toFormValue(
          project.direct_total_project_costs_excluding_overhead
        ),
        implementation_own_contribution: toFormValue(
          project.implementation_own_contribution
        ),
        cash_contribution: toFormValue(project.cash_contribution),
        total_requested_funding: toFormValue(project.total_requested_funding),
        total_requested_funding_including_overhead: toFormValue(
          project.total_requested_funding_including_overhead
        ),
        budget_exception_basis: project.budget_exception_basis ?? "",
        duration_months: toFormValue(project.duration_months),
      })
      setLoadError(false)
    } catch {
      setLoadError(true)
    }
  }, [projectId])

  React.useEffect(() => {
    void loadProject()
  }, [loadProject])

  const set = (patch: Partial<BudgetFormState>) => {
    setSaved(false)
    setForm((prev) => ({ ...prev, ...patch }))
  }

  const onSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    const patch: ProjectBudgetPatch = {}
    for (const field of AMOUNT_FIELDS) {
      const parsed = parseAmount(form[field.key])
      if (parsed === "invalid") {
        setError(`Bitte geben Sie für „${field.label}" einen gültigen Betrag ein.`)
        return
      }
      patch[field.key] = parsed
    }
    const duration = parseDuration(form.duration_months)
    if (duration === "invalid") {
      setError("Bitte geben Sie die Projektdauer als ganze Monate (mindestens 1) ein.")
      return
    }
    patch.duration_months = duration
    patch.budget_exception_basis = form.budget_exception_basis.trim() || null

    setBusy(true)
    setError(null)
    try {
      await patchProject(projectId, patch)
      setSaved(true)
      // Vorprüfung sofort mit den gespeicherten Werten aktualisieren.
      void loadPrecheck()
    } catch {
      setError("Budgetangaben konnten nicht gespeichert werden.")
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="mt-10">
      <h2 className="text-sm font-medium">Budget &amp; Laufzeit</h2>
      <p className="mt-1 text-sm text-muted-foreground">
        Beträge in CHF, direkte Projektkosten ohne Overhead. Die formale
        Bewertung sehen Sie im Schritt Anforderungen.
      </p>

      {loadError && (
        <div
          role="alert"
          className="mt-4 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3"
        >
          <p className="text-sm text-foreground">
            Budgetangaben konnten nicht geladen werden.
          </p>
          <Button type="button" variant="outline" size="sm" onClick={() => void loadProject()}>
            <RefreshCw data-icon="inline-start" />
            Erneut versuchen
          </Button>
        </div>
      )}

      <form
        onSubmit={onSubmit}
        className="mt-4 grid grid-cols-1 gap-4 rounded-lg border border-border bg-card p-4 sm:grid-cols-2"
      >
        {AMOUNT_FIELDS.map((field) => (
          <div key={field.key}>
            <Label htmlFor={`budget-${field.key}`}>{field.label}</Label>
            <Input
              id={`budget-${field.key}`}
              value={form[field.key]}
              onChange={(e) => set({ [field.key]: e.target.value })}
              placeholder="z. B. 250000"
              inputMode="decimal"
            />
            <BudgetImportProvenance
              targetKey={`project.${field.key}`}
              summary={importSummary}
            />
          </div>
        ))}
        <div>
          <Label htmlFor="budget-duration">Projektdauer (Monate)</Label>
          <Input
            id="budget-duration"
            value={form.duration_months}
            onChange={(e) => set({ duration_months: e.target.value })}
            placeholder="z. B. 24"
            inputMode="numeric"
          />
        </div>
        <div>
          <Label htmlFor="budget-exception">Begründung für Ausnahme (optional)</Label>
          <Input
            id="budget-exception"
            value={form.budget_exception_basis}
            onChange={(e) => set({ budget_exception_basis: e.target.value })}
            placeholder="z. B. Start-up-Ausnahme gemäss Vereinbarung"
          />
          <p className="mt-1 text-xs text-muted-foreground">
            Eine Ausnahme führt in der Vorprüfung zur Einstufung «Prüfen» —
            sie wird von Menschen geprüft, nie automatisch akzeptiert.
          </p>
        </div>

        {error && (
          <p role="alert" className="text-sm text-destructive sm:col-span-2">
            {error}
          </p>
        )}
        {saved && (
          <p role="status" className="text-sm text-status-fulfilled sm:col-span-2">
            Budgetangaben gespeichert.
          </p>
        )}

        <div className="sm:col-span-2">
          <Button type="submit" disabled={busy}>
            {busy ? (
              <Loader2 data-icon="inline-start" className="animate-spin" />
            ) : (
              <Save data-icon="inline-start" />
            )}
            Budget speichern
          </Button>
        </div>
      </form>

      <section
        data-testid="budget-precheck"
        className="mt-6 rounded-lg border border-border bg-card p-4"
      >
        <h3 className="text-sm font-medium">Formale Vorprüfung</h3>
        <p className="mt-1 text-xs text-muted-foreground">
          Auf Basis der aktuellen Eingaben, berechnet vom Regelwerk — ersetzt
          weder die Analyse noch die menschliche Prüfung.
        </p>

        {precheckUnavailable && (
          <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm text-muted-foreground">
              Die Vorprüfung ist derzeit nicht verfügbar.
            </p>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => void loadPrecheck()}
            >
              <RefreshCw data-icon="inline-start" />
              Erneut versuchen
            </Button>
          </div>
        )}

        {precheck && (
          <>
            <dl className="mt-3 grid gap-x-6 gap-y-1 text-sm sm:grid-cols-[auto_1fr]">
              <dt className="text-muted-foreground">
                Eigenleistung + Barbeitrag = Umsetzungspartnerbeitrag
              </dt>
              <dd data-testid="precheck-contribution">
                {precheck.figures.implementation_contribution_chf !== null &&
                precheck.figures.own_contribution_chf !== null &&
                precheck.figures.cash_contribution_chf !== null
                  ? `${chf(precheck.figures.own_contribution_chf)} + ${chf(precheck.figures.cash_contribution_chf)} = ${chf(precheck.figures.implementation_contribution_chf)} CHF` +
                    (precheck.figures.implementation_share_percent !== null
                      ? ` (${NUMBER_FORMAT.format(precheck.figures.implementation_share_percent)} % der direkten Projektkosten)`
                      : "")
                  : "Angabe fehlt"}
              </dd>
              <dt className="text-muted-foreground">Barbeitrag (Cash-Anteil)</dt>
              <dd data-testid="precheck-cash">
                {precheck.figures.cash_share_percent !== null
                  ? `${NUMBER_FORMAT.format(precheck.figures.cash_share_percent)} % der direkten Projektkosten`
                  : "Angabe fehlt"}
              </dd>
              <dt className="text-muted-foreground">Förderanteil (informativ)</dt>
              <dd data-testid="precheck-funding">
                {precheck.figures.funding_share_percent !== null
                  ? `${NUMBER_FORMAT.format(precheck.figures.funding_share_percent)} %`
                  : "Angabe fehlt"}
              </dd>
            </dl>

            <ul className="mt-4 flex flex-col gap-2">
              {precheck.checks.map((check) => (
                <li
                  key={check.rule_id}
                  data-testid="precheck-check"
                  className="flex flex-col gap-1 rounded-md border border-border px-3 py-2"
                >
                  <span className="flex flex-wrap items-center gap-2">
                    <Badge
                      variant="outline"
                      className={PRECHECK_BADGE[check.status].className}
                    >
                      {PRECHECK_BADGE[check.status].label}
                    </Badge>
                    <span className="text-sm font-medium text-foreground">
                      {check.title}
                    </span>
                  </span>
                  <span className="text-xs text-muted-foreground">
                    {check.reason}
                  </span>
                  {check.status === "review" && (
                    <span className="text-xs text-status-partial">
                      Die Ausnahmebegründung wird von Menschen geprüft — die
                      App bestätigt keine Ausnahme.
                    </span>
                  )}
                </li>
              ))}
            </ul>

            <Accordion className="mt-2">
              <AccordionItem value="warum" className="border-b-0">
                <AccordionTrigger>Warum wird das geprüft?</AccordionTrigger>
                <AccordionContent>
                  <ul className="flex flex-col gap-2 text-xs text-muted-foreground">
                    {precheck.checks.map((check) => (
                      <li key={check.rule_id}>
                        <span className="font-medium text-foreground">
                          {check.title}:
                        </span>{" "}
                        {conditionSentence(check)}{" "}
                        <span>
                          Quelle: {check.source_ref ?? "—"}
                          {check.last_checked
                            ? ` (geprüft am ${check.last_checked})`
                            : ""}
                          , Regelstand {check.rule_version}.
                        </span>
                      </li>
                    ))}
                    <li>
                      Eine erfüllte Rechnung ist eine formale Vorprüfung — die
                      menschliche Prüfung erfolgt im Schritt Qualitätsprüfung.
                    </li>
                  </ul>
                </AccordionContent>
              </AccordionItem>
            </Accordion>
          </>
        )}
      </section>
    </section>
  )
}

function BudgetImportProvenance({
  targetKey,
  summary,
}: Readonly<{
  targetKey: string
  summary?: StructuredImportSummaryDto | null
}>) {
  const provenance = summary?.provenance.find(
    (entry) => entry.candidate_kind === "budget" && entry.target_key === targetKey
  )
  if (!provenance) return null
  return (
    <p className="mt-1 text-xs text-primary" data-testid="budget-import-provenance">
      {provenance.state === "confirmed"
        ? "Aus PDF übernommen"
        : provenance.state === "changed_after_import"
          ? "Ursprünglich aus PDF übernommen – anschließend geändert"
          : "Aus PDF übernommen – Ziel nicht mehr vorhanden"}
      {provenance.source_location ? ` – ${provenance.source_location}` : ""}
      {provenance.state === "confirmed" ? " – menschlich bestätigt" : ""}
    </p>
  )
}
