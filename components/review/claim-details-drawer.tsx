"use client"

// Teil B4/C — Claim-Level-Details ausschliesslich im Drawer «Technische
// Details»: die normale Qualitätsprüfung zeigt gruppierte Aufgaben; die
// claimgenauen Rohdaten (DraftClaims + Lineage/Suffizienz) bleiben hier
// vollständig einsehbar. Kein Provider-/Modell-Wording, keine Konfidenz-%.

import * as React from "react"
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import {
  getReliability,
  ReliabilityError,
  type ReliabilityClaimDto,
} from "@/lib/reliability"
import { fieldLabel } from "@/lib/review-view"

const CLAIM_TYPE_LABELS: Record<string, string> = {
  market: "Marktaussage",
  innovation: "Innovationsaussage",
  technical: "Technische Aussage",
  partner_fit: "Partner-Fit",
  value_creation: "Wertschöpfung",
  requirement: "Anforderungsbezug",
  budget: "Budgetaussage",
  generic: "Allgemeine Aussage",
}

const STRENGTH_LABELS: Record<string, string> = {
  strong: "stark formuliert",
  moderate: "moderat formuliert",
  weak: "vorsichtig formuliert",
}

const LINEAGE_LABELS: Record<string, string> = {
  direct_evidence: "Direkter Beleg verknüpft",
  indirect_evidence: "Indirekter Beleg vorhanden",
  weak_evidence: "Schwacher Beleg vorhanden",
  no_evidence: "Kein Beleg verknüpft",
  conflicting_evidence: "Widersprüchliche Belege",
  needs_human_review: "Menschliche Prüfung nötig",
}

const SUFFICIENCY_LABELS: Record<string, string> = {
  supports_claim: "Beleg stützt die Aussage",
  weakly_supports_claim: "Beleg stützt die Aussage nur teilweise",
  does_not_support_claim: "Beleg stützt die Aussage nicht",
  insufficient_evidence: "Beleg reicht nicht aus",
  needs_human_review: "Menschliche Prüfung nötig",
}

export function ClaimDetailsDrawer({
  runId,
  fieldId,
  open,
  onOpenChange,
}: {
  runId: string
  /** Optionaler Feldfilter (z. B. aus einer Fix-Queue-Gruppe). */
  fieldId?: string | null
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const [claims, setClaims] = React.useState<ReliabilityClaimDto[] | null>(null)
  const [error, setError] = React.useState<string | null>(null)

  React.useEffect(() => {
    if (!open) return
    let active = true
    getReliability(runId)
      .then((view) => {
        if (!active) return
        setClaims(view.claims)
        setError(null)
      })
      .catch((e) => {
        if (!active) return
        setError(
          e instanceof ReliabilityError
            ? e.message
            : "Die technischen Details konnten nicht geladen werden."
        )
      })
    return () => {
      active = false
    }
  }, [runId, open])

  const visible = (claims ?? []).filter(
    (c) => !fieldId || c.field_id === fieldId
  )

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        className="flex w-[520px] flex-col gap-0 overflow-y-auto p-0 sm:max-w-[520px]"
        data-testid="claim-details-drawer"
      >
        <SheetHeader className="border-b border-border px-6 py-5">
          <SheetTitle className="text-base">Technische Details</SheetTitle>
          <SheetDescription className="text-xs">
            {fieldId
              ? `Alle geprüften Aussagen im Feld «${fieldLabel(fieldId)}».`
              : "Alle geprüften Aussagen dieses Entwurfs."}{" "}
            Beleg-Suffizienzprüfung nach definierten Kriterien — kein Nachweis
            der inhaltlichen Wahrheit.
          </SheetDescription>
        </SheetHeader>

        <div className="flex flex-1 flex-col gap-3 px-6 py-5">
          {error && (
            <p role="alert" className="text-sm text-destructive">
              {error}
            </p>
          )}
          {!error && claims === null && (
            <div className="flex flex-col gap-3">
              {[0, 1, 2].map((i) => (
                <Skeleton key={i} className="h-20 w-full" />
              ))}
            </div>
          )}
          {claims !== null && visible.length === 0 && (
            <p className="text-sm text-muted-foreground">
              Keine geprüften Aussagen vorhanden. Führen Sie die
              Zuverlässigkeitsprüfung aus, um Aussagen zu analysieren.
            </p>
          )}
          {visible.map((claim) => (
            <article
              key={claim.claim_id}
              data-testid="claim-detail"
              className="flex flex-col gap-2 rounded-md border border-border bg-card px-4 py-3"
            >
              <p className="text-sm text-foreground">{claim.claim_text}</p>
              <div className="flex flex-wrap items-center gap-1.5">
                <Badge variant="outline">
                  {CLAIM_TYPE_LABELS[claim.claim_type] ?? "Aussage"}
                </Badge>
                <Badge variant="outline">
                  {STRENGTH_LABELS[claim.strength] ?? claim.strength}
                </Badge>
                {!claim.requires_evidence && (
                  <Badge variant="outline">Kein Beleg erforderlich</Badge>
                )}
              </div>
              <p className="text-xs text-muted-foreground">
                {LINEAGE_LABELS[claim.lineage_status] ?? "Belegstatus offen"}
                {" · "}
                {SUFFICIENCY_LABELS[claim.sufficiency_status] ??
                  "Suffizienz offen"}
              </p>
              {claim.reason && (
                <p className="text-xs text-muted-foreground">{claim.reason}</p>
              )}
              <div className="flex items-center justify-between gap-2">
                <span className="text-xs text-muted-foreground">
                  {fieldLabel(claim.field_id)}
                </span>
                <Button
                  size="xs"
                  variant="ghost"
                  render={
                    <a
                      href={`/editor?field=${encodeURIComponent(claim.field_id)}`}
                    />
                  }
                  nativeButton={false}
                >
                  Im Entwurf öffnen
                </Button>
              </div>
            </article>
          ))}
        </div>
      </SheetContent>
    </Sheet>
  )
}
