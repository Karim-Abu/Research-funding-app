"use client"

import * as React from "react"
import { Trash2, Plus, RefreshCw } from "lucide-react"
import { AppShell } from "@/components/shell/app-shell"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { currentUser, projects, activeProjectId } from "@/lib/mock-data"
import { getActiveProjectId } from "@/lib/intake-store"
import {
  listPartners,
  createPartner,
  deletePartner,
  type PartnerDto,
  type PartnerType,
} from "@/lib/partners"

const PARTNER_TYPE_LABELS: Record<PartnerType, string> = {
  research_partner: "Forschungspartner",
  implementation_partner: "Umsetzungspartner",
  other: "Weitere",
}

interface FormState {
  name: string
  partner_type: PartnerType
  country: string
  swiss_value_creation: "" | "true" | "false"
  research_partner_eligibility_status: string
  personnel_independence_status: string
  financial_independence_status: string
}

const EMPTY_FORM: FormState = {
  name: "",
  partner_type: "research_partner",
  country: "",
  swiss_value_creation: "",
  research_partner_eligibility_status: "",
  personnel_independence_status: "",
  financial_independence_status: "",
}

function tri(value: "" | "true" | "false"): boolean | null {
  if (value === "true") return true
  if (value === "false") return false
  return null
}

function nullable(value: string): string | null {
  return value === "" ? null : value
}

export function PartnerManager() {
  const [partners, setPartners] = React.useState<PartnerDto[]>([])
  const [form, setForm] = React.useState<FormState>(EMPTY_FORM)
  const [error, setError] = React.useState<string | null>(null)
  const [busy, setBusy] = React.useState(false)
  const projectId = React.useMemo(() => getActiveProjectId(), [])

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

  const onSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!projectId || !form.name.trim()) {
      setError("Name und aktives Projekt sind erforderlich.")
      return
    }
    setBusy(true)
    setError(null)
    try {
      await createPartner(projectId, {
        name: form.name.trim(),
        partner_type: form.partner_type,
        country: nullable(form.country),
        swiss_value_creation: tri(form.swiss_value_creation),
        research_partner_eligibility_status:
          (nullable(form.research_partner_eligibility_status) as never) ?? null,
        personnel_independence_status:
          (nullable(form.personnel_independence_status) as never) ?? null,
        financial_independence_status:
          (nullable(form.financial_independence_status) as never) ?? null,
      })
      setForm(EMPTY_FORM)
      await refresh()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Partner konnte nicht angelegt werden.")
    } finally {
      setBusy(false)
    }
  }

  const onDelete = async (partnerId: string) => {
    try {
      await deletePartner(partnerId)
      await refresh()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Partner konnte nicht gelöscht werden.")
    }
  }

  const set = (patch: Partial<FormState>) =>
    setForm((prev) => ({ ...prev, ...patch }))

  return (
    <AppShell user={currentUser} projects={projects} activeProjectId={activeProjectId}>
      <div className="mx-auto max-w-4xl px-6 py-10">
        <header className="mb-6">
          <h1 className="text-xl font-semibold">Partner &amp; Rollen</h1>
          <p className="text-sm text-muted-foreground">
            Erfassen Sie Forschungs- und Umsetzungspartner. Diese Angaben fliessen
            in die formale Prüfung der Fördervoraussetzungen ein.
          </p>
        </header>

        {error && (
          <div
            role="alert"
            className="mb-4 rounded-md border border-destructive/40 bg-destructive/10 px-4 py-2 text-sm text-destructive"
          >
            {error}
          </div>
        )}

        <form
          onSubmit={onSubmit}
          className="mb-8 grid grid-cols-1 gap-4 rounded-lg border border-border bg-card p-4 sm:grid-cols-2"
        >
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
                <option value="true">ja</option>
                <option value="false">nein</option>
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
          <div className="sm:col-span-2">
            <Button type="submit" disabled={busy}>
              <Plus data-icon="inline-start" />
              Partner hinzufügen
            </Button>
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
                  <div className="mt-1 flex flex-wrap gap-2">
                    <Badge variant="secondary">
                      {PARTNER_TYPE_LABELS[p.partner_type]}
                    </Badge>
                    {p.country && <Badge variant="outline">{p.country}</Badge>}
                    {p.research_partner_eligibility_status && (
                      <Badge variant="outline">
                        {p.research_partner_eligibility_status}
                      </Badge>
                    )}
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  aria-label={`Partner ${p.name} löschen`}
                  onClick={() => void onDelete(p.partner_id)}
                >
                  <Trash2 data-icon="inline-start" />
                  Löschen
                </Button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </AppShell>
  )
}
