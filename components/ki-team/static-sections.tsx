import { Ban, Check, ShieldCheck, UserRound, XCircle } from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import { kiTeamTexts } from "@/lib/ki-team-data"

/**
 * Drei statische Erklärsektionen: was die KI nie entscheidet, wo Nutzer:innen
 * prüfen und wie Daten geschützt sind.
 */
export function StaticSections() {
  return (
    <section
      aria-label="Grenzen und Kontrollpunkte"
      className="grid gap-4 lg:grid-cols-2"
    >
      <Card size="sm" className="bg-card/60">
        <CardContent className="flex flex-col gap-3">
          <h2 className="flex items-center gap-2 font-heading text-sm font-medium text-foreground">
            <Ban aria-hidden="true" className="size-4 text-muted-foreground" />
            {kiTeamTexts.nieEntscheidet.titel}
          </h2>
          <ul className="flex flex-col gap-2">
            {kiTeamTexts.nieEntscheidet.punkte.map((punkt) => (
              <li key={punkt} className="flex items-start gap-2 text-sm">
                <XCircle
                  aria-hidden="true"
                  className="mt-0.5 size-4 shrink-0 text-muted-foreground"
                />
                <span>{punkt}</span>
              </li>
            ))}
          </ul>
          <p className="mt-1 rounded-lg border border-border bg-muted/40 px-3 py-2 text-sm font-medium text-foreground">
            {kiTeamTexts.nieEntscheidet.schlusssatz}
          </p>
        </CardContent>
      </Card>

      <Card size="sm" className="bg-card/60">
        <CardContent className="flex flex-col gap-3">
          <h2 className="flex items-center gap-2 font-heading text-sm font-medium text-foreground">
            <UserRound aria-hidden="true" className="size-4 text-status-partial" />
            {kiTeamTexts.woSiePruefen.titel}
          </h2>
          <ul className="flex flex-col gap-2">
            {kiTeamTexts.woSiePruefen.punkte.map((punkt) => (
              <li key={punkt.phase} className="flex items-start gap-2 text-sm">
                <span
                  aria-hidden="true"
                  className="mt-0.5 shrink-0 text-status-partial"
                >
                  ●
                </span>
                <span>
                  <span className="font-medium">{punkt.phase}:</span> {punkt.text}
                </span>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>

      <Card size="sm" className="bg-muted/35 lg:col-span-2">
        <CardContent className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <h2 className="flex shrink-0 items-center gap-2 font-heading text-sm font-medium text-foreground">
            <ShieldCheck
              aria-hidden="true"
              className="size-4 text-status-fulfilled"
            />
            {kiTeamTexts.datenSchutz.titel}
          </h2>
          <ul className="flex flex-wrap gap-2">
            {kiTeamTexts.datenSchutz.regeln.map((regel) => (
              <li
                key={regel}
                className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-2.5 py-1 text-xs text-foreground"
              >
                <Check
                  aria-hidden="true"
                  className="size-3.5 shrink-0 text-status-fulfilled"
                />
                {regel}
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>
    </section>
  )
}
