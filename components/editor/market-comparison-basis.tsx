"use client"

// Vergleichsbasis — makes explicit "das ist deine Projektidee, dagegen wurde
// verglichen". Read-only display of the project's own idea (confidential project
// description, never sent out) plus the public-safe search focus the market
// search actually used. Shared by the sheet, the editor rail and the Quellen
// section. Editing the idea happens where it is entered (/intake).

import { Info, Pencil, Target } from "lucide-react"
import { Button } from "@/components/ui/button"
import type { ComparisonBasisDto } from "@/lib/market-comparison"

export function MarketComparisonBasis({
  basis,
  compact = false,
}: {
  basis: ComparisonBasisDto
  compact?: boolean
}) {
  if (compact) {
    return (
      <div
        data-testid="market-basis-compact"
        className="rounded-md border border-border bg-muted/20 px-3 py-2"
      >
        <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
          Vergleichsbasis
        </p>
        <p className="text-[11px] text-foreground">
          <span className="font-medium">{basis.title}</span> — dagegen wird verglichen.
        </p>
      </div>
    )
  }

  return (
    <section
      data-testid="market-basis"
      className="flex flex-col gap-2 rounded-lg border border-border bg-muted/20 px-4 py-3"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-1.5">
          <Target aria-hidden className="size-3.5 text-muted-foreground" />
          <h3 className="text-xs font-semibold text-foreground">Vergleichsbasis</h3>
        </div>
        <Button
          size="xs"
          variant="ghost"
          render={<a href="/intake" />}
          nativeButton={false}
        >
          <Pencil aria-hidden className="size-3" />
          Projektidee bearbeiten
        </Button>
      </div>
      <p className="text-[11px] text-muted-foreground">Dagegen wird verglichen.</p>

      <div>
        <p className="text-[11px] font-medium text-muted-foreground">Deine Projektidee</p>
        <p className="text-xs font-semibold text-foreground">{basis.title}</p>
        {basis.idea && (
          <p className="mt-0.5 whitespace-pre-line text-xs text-foreground">{basis.idea}</p>
        )}
        {basis.innovation_field && (
          <p className="mt-0.5 text-[11px] text-muted-foreground">
            Innovationsfeld: {basis.innovation_field}
          </p>
        )}
      </div>

      {(basis.search_focus || basis.search_aspects.length > 0) && (
        <div className="border-t border-border pt-2">
          <p className="flex items-center gap-1.5 text-[11px] font-medium text-muted-foreground">
            <Info aria-hidden className="size-3" />
            Untersuchter Suchfokus (öffentlich-sichere Recherche)
          </p>
          {basis.search_focus && (
            <p className="mt-0.5 text-xs text-foreground">{basis.search_focus}</p>
          )}
          {basis.search_aspects.length > 0 && (
            <ul className="mt-1 flex flex-wrap gap-1">
              {basis.search_aspects.map((aspect) => (
                <li
                  key={aspect}
                  className="rounded-full bg-muted px-2 py-0.5 text-[11px] text-muted-foreground"
                >
                  {aspect}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </section>
  )
}
