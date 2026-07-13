"use client"

// Partner & Budget (Demo-Workflow): Partner anlegen, BEARBEITEN und entfernen
// mit den MVP-Pflichtfeldern; Detailfragen (Unabhängigkeit) progressiv
// eingeblendet. Qualitative Angaben werden nie automatisch bewertet — die
// Liste markiert sie nur mit «Menschliche Prüfung erforderlich».

import * as React from "react"
import { Trash2, Plus, Pencil, RefreshCw, Save, X } from "lucide-react"
import { AppShell } from "@/components/shell/app-shell"
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { Textarea } from "@/components/ui/textarea"
import { currentUser, projects, activeProjectId } from "@/lib/mock-data"
import { getActiveProjectId } from "@/lib/intake-store"
import {
  listPartners,
  createPartner,
  updatePartner,
  deletePartner,
  type IndependenceStatus,
  type PartnerDto,
  type PartnerInput,
  type PartnerType,
  type ResearchEligibility,
} from "@/lib/partners"
import { BudgetForm } from "@/components/partner/budget-form"

const PARTNER_TYPE_LABELS: Record<PartnerType, string> = {
  research_partner: "Forschungspartner",
  implementation_partner: "Umsetzungspartner",
  other: "Weitere",
}

const INDEPENDENCE_LABELS: Record<IndependenceStatus, string> = {
  confirmed: "bestätigt",
  exception: "Ausnahme beantragt",
  needs_input: "Angabe nötig",
}

// Deutsche Anzeige der Beitragsberechtigung — nie rohe Enum-Werte in der UI.
const ELIGIBILITY_LABELS: Record<ResearchEligibility, string> = {
  eligible: "beitragsberechtigt",
  not_eligible: "nicht beitragsberechtigt",
  needs_verification: "zu prüfen",
}

interface FormState {
  name: string
  partner_type: PartnerType
  project_role: string
  country: string
  contribution: string
  swiss_value_creation: "" | "true" | "false"
  research_partner_eligibility_status: string
  personnel_independence_status: string
  financial_independence_status: string
  review_comment: string
}

const EMPTY_FORM: FormState = {
  name: "",
  partner_type: "research_partner",
  project_role: "",
  country: "",
  contribution: "",
  swiss_value_creation: "",
  research_partner_eligibility_status: "",
  personnel_independence_status: "",
  financial_independence_status: "",
  review_comment: "",
}

function tri(value: "" | "true" | "false"): boolean | null {
  if (value === "true") return true
  if (value === "false") return false
  return null
}

function nullable(value: string): string | null {
  return value === "" ? null : value
}

/** Explizit unklar/nicht bestätigt → kurze Begründung ist Pflicht
 *  (spiegelt die Backend-Konsistenzregel; nie ein automatisches Urteil). */
function needsComment(form: FormState): boolean {
  const unclear = ["exception", "needs_input"]
  return (
    unclear.includes(form.personnel_independence_status) ||
    unclear.includes(form.financial_independence_status) ||
    ["not_eligible", "needs_verification"].includes(
      form.research_partner_eligibility_status
    ) ||
    form.swiss_value_creation === "false"
  )
}

/** MVP-Pflichtfelder — deutsche Feldnamen für den Disabled-Hinweis. */
function missingFields(form: FormState): string[] {
  const missing: string[] = []
  if (!form.name.trim()) missing.push("Name")
  if (!form.country.trim()) missing.push("Land")
  if (!form.project_role.trim()) missing.push("Rolle im Projekt")
  if (!form.contribution.trim()) missing.push("Kompetenz & Beitrag")
  if (needsComment(form) && !form.review_comment.trim()) {
    missing.push("Kommentar zur Einstufung")
  }
  return missing
}

/** Qualitative Angabe offen/unklar → HITL-Markierung in der Liste. */
function needsHumanReview(p: PartnerDto): boolean {
  const unclear: (string | null | undefined)[] = ["exception", "needs_input"]
  return (
    unclear.includes(p.personnel_independence_status) ||
    unclear.includes(p.financial_independence_status) ||
    p.research_partner_eligibility_status === "needs_verification" ||
    p.research_partner_eligibility_status === "not_eligible" ||
    p.swiss_value_creation === false
  )
}

function formFromPartner(p: PartnerDto): FormState {
  let swiss: FormState["swiss_value_creation"] = ""
  if (p.swiss_value_creation === true) swiss = "true"
  if (p.swiss_value_creation === false) swiss = "false"
  return {
    name: p.name,
    partner_type: p.partner_type,
    project_role: p.project_role ?? "",
    country: p.country ?? "",
    contribution: p.contribution ?? "",
    swiss_value_creation: swiss,
    research_partner_eligibility_status:
      p.research_partner_eligibility_status ?? "",
    personnel_independence_status: p.personnel_independence_status ?? "",
    financial_independence_status: p.financial_independence_status ?? "",
    review_comment: p.review_comment ?? "",
  }
}

function toInput(form: FormState): PartnerInput {
  return {
    name: form.name.trim(),
    partner_type: form.partner_type,
    project_role: nullable(form.project_role.trim()),
    country: nullable(form.country.trim()),
    contribution: nullable(form.contribution.trim()),
    swiss_value_creation: tri(form.swiss_value_creation),
    research_partner_eligibility_status:
      (nullable(form.research_partner_eligibility_status) as never) ?? null,
    personnel_independence_status:
      (nullable(form.personnel_independence_status) as never) ?? null,
    financial_independence_status:
      (nullable(form.financial_independence_status) as never) ?? null,
    review_comment: nullable(form.review_comment.trim()),
  }
}

export function PartnerManager() {
  const [partners, setPartners] = React.useState<PartnerDto[]>([])
  const [form, setForm] = React.useState<FormState>(EMPTY_FORM)
  const [editingId, setEditingId] = React.useState<string | null>(null)
  const [error, setError] = React.useState<string | null>(null)
  const [busy, setBusy] = React.useState(false)
  const [projectId, setProjectId] = React.useState<string | null>(null)
  const [projectResolved, setProjectResolved] = React.useState(false)

  React.useEffect(() => {
    setProjectId(getActiveProjectId())
    setProjectResolved(true)
  }, [])

  const refresh = React.useCallback(async () => {
    if (!projectId) return
    try {
      setPartners(await listPartners(projectId))
    } catch (e) {
      setError(e instanceof Error ? e.message : "Fehler beim Laden.")
    }
  }, [projectId])

  React.useEffect(() => {
    void refresh()
  }, [refresh])

  const missing = missingFields(form)
  const commentRequired = needsComment(form)
  const editing = editingId !== null
  // Beim Bearbeiten mit gesetzten Detailangaben startet der Abschnitt offen.
  const independenceOpen =
    form.personnel_independence_status !== "" ||
    form.financial_independence_status !== ""

  const startEdit = (p: PartnerDto) => {
    setEditingId(p.partner_id)
    setForm(formFromPartner(p))
    setError(null)
  }

  const cancelEdit = () => {
    setEditingId(null)
    setForm(EMPTY_FORM)
    setError(null)
  }

  const onSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!projectId || missing.length > 0) return
    setBusy(true)
    setError(null)
    try {
      if (editingId) {
        await updatePartner(editingId, toInput(form))
      } else {
        await createPartner(projectId, toInput(form))
      }
      setEditingId(null)
      setForm(EMPTY_FORM)
      await refresh()
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : "Der Partner konnte nicht gespeichert werden."
      )
    } finally {
      setBusy(false)
    }
  }

  const onDelete = async (partnerId: string) => {
    try {
      await deletePartner(partnerId)
      if (partnerId === editingId) cancelEdit()
      await refresh()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Partner konnte nicht gelöscht werden.")
    }
  }

  const set = (patch: Partial<FormState>) =>
    setForm((prev) => ({ ...prev, ...patch }))

  return (
    <AppShell
      user={currentUser}
      projects={projects}
      activeProjectId={activeProjectId}
    >
      <div className="mx-auto max-w-4xl px-6 py-10">
        <header className="mb-6">
          <h1 className="text-xl font-semibold">Partner &amp; Budget</h1>
          <p className="text-sm text-muted-foreground">
            Erfassen Sie Forschungs- und Umsetzungspartner sowie die Budgeteckwerte.
            Diese Angaben fliessen in die formale Prüfung der Fördervoraussetzungen ein.
          </p>
        </header>

        {error && (
          <div
            role="alert"
            className="mb-4 flex flex-wrap items-center justify-between gap-2 rounded-md border border-destructive/40 bg-destructive/10 px-4 py-2 text-sm text-destructive"
          >
            <span>{error}</span>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => {
                setError(null)
                void refresh()
              }}
            >
              <RefreshCw data-icon="inline-start" />
              Erneut versuchen
            </Button>
          </div>
        )}

        <form
          onSubmit={onSubmit}
          className="mb-8 grid grid-cols-1 gap-4 rounded-lg border border-border bg-card p-4 sm:grid-cols-2"
        >
          {editing && (
            <p className="text-sm font-medium text-foreground sm:col-span-2">
              Partner bearbeiten: {form.name || "…"}
            </p>
          )}
          <div className="sm:col-span-2">
            <Label htmlFor="p-name">Name</Label>
            <Input
              id="p-name"
              value={form.name}
              onChange={(e) => set({ name: e.target.value })}
              placeholder="z. B. ETH Zürich"
            />
          </div>
          <div>
            <Label htmlFor="p-type">Partnertyp</Label>
            <select
              id="p-type"
              className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={form.partner_type}
              onChange={(e) => set({ partner_type: e.target.value as PartnerType })}
            >
              <option value="research_partner">Forschungspartner</option>
              <option value="implementation_partner">Umsetzungspartner</option>
              <option value="other">Weitere</option>
            </select>
          </div>
          <div>
            <Label htmlFor="p-country">Land</Label>
            <Input
              id="p-country"
              value={form.country}
              onChange={(e) => set({ country: e.target.value })}
              placeholder="CH"
            />
          </div>
          <div className="sm:col-span-2">
            <Label htmlFor="p-role">Rolle im Projekt</Label>
            <Input
              id="p-role"
              value={form.project_role}
              onChange={(e) => set({ project_role: e.target.value })}
              placeholder="z. B. Entwicklung des Prototyps"
            />
          </div>
          <div className="sm:col-span-2">
            <Label htmlFor="p-contribution">Kompetenz &amp; Beitrag (kurz)</Label>
            <Textarea
              id="p-contribution"
              rows={2}
              value={form.contribution}
              onChange={(e) => set({ contribution: e.target.value })}
              placeholder="z. B. Langjährige Erfahrung in Leistungselektronik; baut den Prototyp."
            />
          </div>
          {form.partner_type === "implementation_partner" && (
            <div>
              <Label htmlFor="p-svc">Wertschöpfung in der Schweiz</Label>
              <select
                id="p-svc"
                className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={form.swiss_value_creation}
                onChange={(e) =>
                  set({ swiss_value_creation: e.target.value as FormState["swiss_value_creation"] })
                }
              >
                <option value="">unbekannt</option>
                <option value="true">bestätigt</option>
                <option value="false">nicht bestätigt</option>
              </select>
            </div>
          )}
          {form.partner_type === "research_partner" && (
            <div>
              <Label htmlFor="p-elig">Beitragsberechtigung</Label>
              <select
                id="p-elig"
                className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={form.research_partner_eligibility_status}
                onChange={(e) =>
                  set({ research_partner_eligibility_status: e.target.value })
                }
              >
                <option value="">unbekannt</option>
                <option value="eligible">beitragsberechtigt</option>
                <option value="not_eligible">nicht beitragsberechtigt</option>
                <option value="needs_verification">zu prüfen</option>
              </select>
            </div>
          )}

          {/* Detailfragen progressiv: eingeklappt, bis sie gebraucht werden. */}
          <div className="sm:col-span-2">
            <Accordion
              key={editingId ?? "add"}
              defaultValue={independenceOpen ? ["independence"] : []}
            >
              <AccordionItem value="independence" className="border-b-0">
                <AccordionTrigger>Unabhängigkeit (Detailangaben)</AccordionTrigger>
                <AccordionContent>
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    <div>
                      <Label htmlFor="p-pers">Personelle Unabhängigkeit</Label>
                      <select
                        id="p-pers"
                        className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                        value={form.personnel_independence_status}
                        onChange={(e) =>
                          set({ personnel_independence_status: e.target.value })
                        }
                      >
                        <option value="">unbekannt</option>
                        <option value="confirmed">bestätigt</option>
                        <option value="exception">Ausnahme beantragt</option>
                        <option value="needs_input">Angabe nötig</option>
                      </select>
                    </div>
                    <div>
                      <Label htmlFor="p-fin">Finanzielle Unabhängigkeit</Label>
                      <select
                        id="p-fin"
                        className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                        value={form.financial_independence_status}
                        onChange={(e) =>
                          set({ financial_independence_status: e.target.value })
                        }
                      >
                        <option value="">unbekannt</option>
                        <option value="confirmed">bestätigt</option>
                        <option value="exception">Ausnahme beantragt</option>
                        <option value="needs_input">Angabe nötig</option>
                      </select>
                    </div>
                  </div>
                </AccordionContent>
              </AccordionItem>
            </Accordion>
          </div>

          {commentRequired && (
            <div className="sm:col-span-2">
              <Label htmlFor="p-comment">Kommentar zur Einstufung</Label>
              <Textarea
                id="p-comment"
                rows={2}
                value={form.review_comment}
                onChange={(e) => set({ review_comment: e.target.value })}
                placeholder="Kurze Begründung, warum die Angabe unklar oder nicht bestätigt ist."
              />
              <p className="mt-1 text-xs text-muted-foreground">
                Pflicht bei «unklar/nicht bestätigt» — die Einschätzung bleibt
                eine menschliche Prüfung, die App bewertet nichts automatisch.
              </p>
            </div>
          )}

          <div className="flex flex-wrap items-center gap-3 sm:col-span-2">
            <Button type="submit" disabled={busy || missing.length > 0}>
              {editing ? (
                <Save data-icon="inline-start" />
              ) : (
                <Plus data-icon="inline-start" />
              )}
              {editing ? "Änderungen speichern" : "Partner hinzufügen"}
            </Button>
            {editing && (
              <Button type="button" variant="outline" onClick={cancelEdit}>
                <X data-icon="inline-start" />
                Abbrechen
              </Button>
            )}
            {missing.length > 0 && (
              <p className="text-xs text-muted-foreground">
                Noch offen: {missing.join(", ")}.
              </p>
            )}
          </div>
        </form>

        <div className="flex items-center justify-between">
          <h2 className="text-sm font-medium">Erfasste Partner ({partners.length})</h2>
          <Button variant="ghost" size="sm" onClick={() => void refresh()}>
            <RefreshCw data-icon="inline-start" />
            Aktualisieren
          </Button>
        </div>

        {partners.length === 0 ? (
          <p className="mt-4 rounded-md border border-dashed border-border px-4 py-8 text-center text-sm text-muted-foreground">
            Noch keine Partner erfasst.
          </p>
        ) : (
          <ul className="mt-4 divide-y divide-border rounded-lg border border-border">
            {partners.map((p) => (
              <li key={p.partner_id} className="flex items-center justify-between gap-4 px-4 py-3">
                <div>
                  <p className="text-sm font-medium">{p.name}</p>
                  {p.project_role && (
                    <p className="text-xs text-muted-foreground">{p.project_role}</p>
                  )}
                  {p.contribution && (
                    <p className="text-xs text-muted-foreground">{p.contribution}</p>
                  )}
                  <div className="mt-1 flex flex-wrap gap-2">
                    <Badge variant="secondary">
                      {PARTNER_TYPE_LABELS[p.partner_type]}
                    </Badge>
                    {p.country && <Badge variant="outline">{p.country}</Badge>}
                    {p.research_partner_eligibility_status && (
                      <Badge variant="outline">
                        {ELIGIBILITY_LABELS[p.research_partner_eligibility_status]}
                      </Badge>
                    )}
                    {p.swiss_value_creation !== null &&
                      p.swiss_value_creation !== undefined && (
                        <Badge variant="outline">
                          {`CH-Wertschöpfung: ${p.swiss_value_creation ? "bestätigt" : "nicht bestätigt"}`}
                        </Badge>
                      )}
                    {p.personnel_independence_status && (
                      <Badge variant="outline">
                        {`Personell: ${INDEPENDENCE_LABELS[p.personnel_independence_status]}`}
                      </Badge>
                    )}
                    {p.financial_independence_status && (
                      <Badge variant="outline">
                        {`Finanziell: ${INDEPENDENCE_LABELS[p.financial_independence_status]}`}
                      </Badge>
                    )}
                    {needsHumanReview(p) && (
                      <Badge
                        variant="outline"
                        className="border-status-partial/60 text-status-partial"
                      >
                        Menschliche Prüfung erforderlich
                      </Badge>
                    )}
                  </div>
                  {p.review_comment && (
                    <p className="mt-1 text-xs text-muted-foreground">
                      Kommentar: {p.review_comment}
                    </p>
                  )}
                </div>
                <div className="flex shrink-0 items-center gap-1">
                  <Button
                    variant="ghost"
                    size="sm"
                    aria-label={`Partner ${p.name} bearbeiten`}
                    onClick={() => startEdit(p)}
                  >
                    <Pencil data-icon="inline-start" />
                    Bearbeiten
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    aria-label={`Partner ${p.name} löschen`}
                    onClick={() => void onDelete(p.partner_id)}
                  >
                    <Trash2 data-icon="inline-start" />
                    Löschen
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}

        {projectResolved && !projectId && (
          <p className="mt-10 rounded-md border border-dashed border-border px-4 py-6 text-center text-sm text-muted-foreground">
            Kein aktives Projekt ausgewählt.
          </p>
        )}
        {projectResolved && projectId && <BudgetForm projectId={projectId} />}
      </div>
    </AppShell>
  )
}
