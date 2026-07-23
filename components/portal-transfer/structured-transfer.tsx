"use client"

import * as React from "react"
import { Check, Copy, Info } from "lucide-react"
import { Button } from "@/components/ui/button"
import { copyPlain } from "@/lib/clipboard"
import {
  recordStructuredCopyEvent,
  type StructuredCopyTarget,
  type TransferSnapshotDto,
} from "@/lib/portal-transfer"

function money(value: number | null): string {
  return value == null ? "Nicht angegeben" : `CHF ${value.toLocaleString("de-CH", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function partnerCellTarget(index: number, key: string) {
  return `partner:${index}:${key}`
}

// Deutsche Spaltennamen für Kopier-Beschriftungen — rohe Feld-Keys erreichen
// die UI (auch den a11y-Tree) nicht.
const PARTNER_COLUMN_LABELS: Record<string, string> = {
  name: "Partner",
  partner_type: "Typ",
  project_role: "Rolle",
  country: "Land",
  research_partner_eligibility_status: "Prüfstatus",
}

function CopyValue({ runId, enabled, targetType, targetKey, value, label, iconOnly = false, text = "Kopieren" }: Readonly<{
  runId: string | null
  enabled: boolean
  targetType: StructuredCopyTarget
  targetKey: string
  value: string
  label: string
  /** Leiser Icon-Button direkt neben dem Wert (Zellen-Kopie in der Tabelle). */
  iconOnly?: boolean
  text?: string
}>) {
  const [copied, setCopied] = React.useState(false)
  const [note, setNote] = React.useState<string | null>(null)
  async function copy() {
    setNote(null)
    if (enabled && runId) {
      try {
        await recordStructuredCopyEvent(runId, targetType, targetKey)
      } catch {
        setNote("Kopierversuch konnte nicht protokolliert werden.")
      }
    }
    try {
      await copyPlain(value)
      setCopied(true)
    } catch {
      setNote("Automatisches Kopieren ist nicht möglich.")
    }
  }
  if (iconOnly) {
    return (
      <span className="inline-flex flex-col items-start gap-1">
        <Button
          type="button"
          size="icon-xs"
          variant="ghost"
          className="text-muted-foreground"
          onClick={() => void copy()}
          aria-label={label}
          title={label}
        >
          {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
        </Button>
        {note && <span role="status" className="text-[11px] text-muted-foreground">{note}</span>}
      </span>
    )
  }
  return (
    <span className="inline-flex flex-col items-start gap-1">
      <Button type="button" size="sm" variant="outline" onClick={() => void copy()} aria-label={label}>
        {copied ? <Check data-icon="inline-start" /> : <Copy data-icon="inline-start" />}
        {copied ? "Kopiert" : text}
      </Button>
      {note && <span role="status" className="text-[11px] text-muted-foreground">{note}</span>}
    </span>
  )
}

export function StructuredTransfer({
  snapshot,
  runId,
  copyEventsEnabled,
}: Readonly<{
  snapshot: TransferSnapshotDto | null
  runId: string | null
  copyEventsEnabled: boolean
}>) {
  const storageKey = runId ? `innolink-transfer-progress:${runId}` : null
  const [checked, setChecked] = React.useState<Set<string>>(new Set())
  React.useEffect(() => {
    if (!storageKey) return
    try {
      const saved = JSON.parse(sessionStorage.getItem(storageKey) ?? "[]")
      if (Array.isArray(saved) && saved.every((item) => typeof item === "string")) setChecked(new Set(saved))
    } catch {
      // The local work marker is optional and never contains copied values.
    }
  }, [storageKey])
  function toggle(reference: string) {
    setChecked((old) => {
      const next = new Set(old)
      if (next.has(reference)) next.delete(reference)
      else next.add(reference)
      if (storageKey) sessionStorage.setItem(storageKey, JSON.stringify([...next]))
      return next
    })
  }

  if (!snapshot) return null
  if (!snapshot.snapshot_available) {
    return <p className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-900">{snapshot.stale_message}</p>
  }
  return (
    <section className="flex flex-col gap-4 rounded-lg border border-border bg-card p-4" aria-label="Strukturierte Übernahme">
      <div>
        <h2 className="text-sm font-semibold">Strukturierte Daten aus dem Run-Snapshot</h2>
        <p className="mt-1 flex items-start gap-2 text-xs text-muted-foreground"><Info className="mt-0.5 size-3.5 shrink-0" />Es wird nichts synchronisiert oder eingereicht. Ein Kopierversuch belegt keine erfolgreiche Portaleingabe.</p>
        {snapshot.stale_message && <p className="mt-2 text-xs text-amber-900">{snapshot.stale_message}</p>}
      </div>

      <div className="rounded-md border border-border p-3">
        <h3 className="text-xs font-semibold">Dauer und Antragssprache</h3>
        <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
          <span>Dauer: {snapshot.project.duration_months == null ? "Nicht angegeben" : `${snapshot.project.duration_months} Monate`}</span>
          {snapshot.project.duration_months != null && <CopyValue runId={runId} enabled={copyEventsEnabled} targetType="duration" targetKey="duration" value={String(snapshot.project.duration_months)} label="Dauer kopieren" />}
          <span className="text-muted-foreground">Antragssprache: noch in Innolink festlegen</span>
        </div>
      </div>

      <div>
        <h3 className="text-xs font-semibold">Partner</h3>
        <div className="mt-2 overflow-x-auto">
          <table className="w-full min-w-[760px] text-left text-xs">
            <thead><tr className="border-b border-border text-muted-foreground"><th className="p-2">Partner</th><th className="p-2">Typ</th><th className="p-2">Rolle</th><th className="p-2">Land</th><th className="p-2">Prüfstatus</th><th className="p-2">Übernahme</th></tr></thead>
            <tbody>{snapshot.partners.map((partner) => {
              const rowText = [partner.name, partner.partner_type, partner.project_role, partner.country, partner.eligibility_status].join("\t")
              // Kopiert wird immer der Portalwert (Roh-Feld) — angezeigt das Label.
              const cells: Array<[key: string, displayed: React.ReactNode, copyValue: string]> = [
                ["name", partner.name, partner.name],
                ["partner_type", partner.partner_type_label ?? partner.partner_type, partner.partner_type],
                ["project_role", partner.project_role, partner.project_role],
                ["country", partner.country, partner.country],
                ["research_partner_eligibility_status", partner.eligibility_status_label ?? partner.eligibility_status, partner.eligibility_status],
              ]
              return (
                <tr key={partner.copy_target_row} className="border-b border-border/60 align-top">
                  {cells.map(([key, displayed, copyValue]) => (
                    <td key={key} className="p-2">
                      <span className="inline-flex items-center gap-1">
                        {displayed}
                        <CopyValue
                          runId={runId}
                          enabled={copyEventsEnabled}
                          targetType="partner_cell"
                          targetKey={partnerCellTarget(partner.index, key)}
                          value={copyValue}
                          label={`${PARTNER_COLUMN_LABELS[key] ?? key} kopieren`}
                          iconOnly
                        />
                      </span>
                    </td>
                  ))}
                  <td className="p-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <CopyValue
                        runId={runId}
                        enabled={copyEventsEnabled}
                        targetType="partner_row"
                        targetKey={partner.copy_target_row}
                        value={rowText}
                        label="Zeile kopieren"
                        text="Zeile kopieren"
                      />
                      <label className="flex items-center gap-1 whitespace-nowrap"><input type="checkbox" checked={checked.has(partner.copy_target_row)} onChange={() => toggle(partner.copy_target_row)} />erfasst</label>
                    </div>
                  </td>
                </tr>
              )
            })}</tbody>
          </table>
        </div>
      </div>

      <div>
        <h3 className="text-xs font-semibold">Budget</h3>
        <div className="mt-2 grid gap-2 sm:grid-cols-2">{snapshot.budget.values.map((item) => <div key={item.copy_target} className="flex flex-wrap items-center justify-between gap-2 rounded border border-border px-3 py-2 text-xs"><span><span className="font-medium">{item.label}:</span> {money(item.value)}</span><span className="flex items-center gap-2"><CopyValue runId={runId} enabled={copyEventsEnabled} targetType="budget_value" targetKey={item.copy_target} value={item.value == null ? "" : String(item.value)} label={`${item.label} kopieren`} /><label className="flex items-center gap-1"><input type="checkbox" checked={checked.has(item.copy_target)} onChange={() => toggle(item.copy_target)} />erfasst</label></span></div>)}</div>
        {snapshot.budget.ratios.map((ratio) => <p key={ratio.label} className="mt-1 text-xs text-muted-foreground">{ratio.label}: {ratio.value.toLocaleString("de-CH", { style: "percent", maximumFractionDigits: 1 })}</p>)}
      </div>
    </section>
  )
}
