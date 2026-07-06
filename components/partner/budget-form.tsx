"use client"

import * as React from "react"
import { Loader2, Save } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  getProject,
  patchProject,
  type ProjectBudgetPatch,
  type ProjectDto,
} from "@/lib/projects"

// Budgeteckwerte (Slice 1): reine Erfassung — die Bewertung (40-60%-Anteil,
// 5%-Barbeitrag) erfolgt deterministisch im Anforderungen-Screen.

interface BudgetFormState {
  direct_total_project_costs_excluding_overhead: string
  implementation_own_contribution: string
  cash_contribution: string
  total_requested_funding: string
  budget_exception_basis: string
  duration_months: string
}

const EMPTY: BudgetFormState = {
  direct_total_project_costs_excluding_overhead: "",
  implementation_own_contribution: "",
  cash_contribution: "",
  total_requested_funding: "",
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

export function BudgetForm({ projectId }: { projectId: string }) {
  const [form, setForm] = React.useState<BudgetFormState>(EMPTY)
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const [saved, setSaved] = React.useState(false)

  React.useEffect(() => {
    let cancelled = false
    getProject(projectId)
      .then((project: ProjectDto) => {
        if (cancelled) return
        setForm({
          direct_total_project_costs_excluding_overhead: toFormValue(
            project.direct_total_project_costs_excluding_overhead
          ),
          implementation_own_contribution: toFormValue(
            project.implementation_own_contribution
          ),
          cash_contribution: toFormValue(project.cash_contribution),
          total_requested_funding: toFormValue(project.total_requested_funding),
          budget_exception_basis: project.budget_exception_basis ?? "",
          duration_months: toFormValue(project.duration_months),
        })
      })
      .catch(() => {
        if (!cancelled) setError("Budgetangaben konnten nicht geladen werden.")
      })
    return () => {
      cancelled = true
    }
  }, [projectId])

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
    </section>
  )
}
