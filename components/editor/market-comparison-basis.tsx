"use client"

// Vergleichsbasis — makes explicit "das ist deine Projektidee, dagegen wurde
// verglichen". Read-only display of the project's own idea (confidential project
// description, never sent out) plus the public-safe search focus the market
// search actually used. Shared by the sheet and the Quellen section (the
// editor rail shows only a one-line "Verglichen mit" summary instead).
// Editing the idea happens where it is entered (/intake).
//
// `collapsible` legt die Basis hinter einen Aufklapper, dessen Titelzeile schon
// Projekt und Innovationsfeld nennt: auf Flächen, die eine Antwort tragen
// sollen, ist die Basis Kontext — nicht das Ergebnis.

import { Pencil, Target } from "lucide-react"
import { Button } from "@/components/ui/button"
import { MarketDisclosure } from "@/components/editor/market-blocks"
import type { ComparisonBasisDto } from "@/lib/market-comparison"

export function MarketComparisonBasis({
  basis,
  collapsible = false,
}: {
  basis: ComparisonBasisDto
  collapsible?: boolean
}) {
  if (collapsible) {
    const summary = [basis.title, basis.innovation_field].filter(Boolean).join(" · ")
    return (
      <MarketDisclosure
        testId="market-basis"
        icon={<Target aria-hidden className="size-3.5 shrink-0 text-muted-foreground" />}
        summary={
          <>
            <span className="text-muted-foreground">Vergleichsbasis: </span>
            {summary}
          </>
        }
      >
        {/* Titel und Innovationsfeld stehen bereits in der Titelzeile. */}
        <BasisBody basis={basis} showTitle={false} />
      </MarketDisclosure>
    )
  }

  return (
    <section
      data-testid="market-basis"
      className="flex flex-col gap-2.5 rounded-md border border-border bg-muted/20 px-4 py-3"
    >
      <div className="flex items-center gap-1.5">
        <Target aria-hidden className="size-3.5 text-muted-foreground" />
        <h3 className="text-xs font-medium text-foreground">Vergleichsbasis</h3>
      </div>
      <BasisBody basis={basis} showTitle />
    </section>
  )
}

function BasisBody({
  basis,
  showTitle,
}: {
  basis: ComparisonBasisDto
  showTitle: boolean
}) {
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-col gap-1">
        {/* R2: «Vergleichsbasis» (Überschrift) und «Deine Projektidee» sagen
            bereits, was hier steht — ein dritter Erklärsatz entfällt. */}
        <p className="text-xs font-medium text-muted-foreground">
          Deine Projektidee — dagegen wird verglichen.
        </p>
        {showTitle && (
          <p className="text-sm font-medium text-foreground">{basis.title}</p>
        )}
        {basis.idea && (
          <p className="whitespace-pre-line text-xs leading-relaxed text-foreground">
            {basis.idea}
          </p>
        )}
        {showTitle && basis.innovation_field && (
          <p className="text-xs text-muted-foreground">
            Innovationsfeld: {basis.innovation_field}
          </p>
        )}
      </div>

      {(basis.search_focus || basis.search_aspects.length > 0) && (
        <div className="flex flex-col gap-1 border-t border-border pt-2.5">
          <p className="text-xs font-medium text-muted-foreground">
            Suchfokus (öffentlich-sichere Recherche)
          </p>
          {basis.search_focus && (
            <p className="text-xs leading-relaxed text-foreground">{basis.search_focus}</p>
          )}
          {basis.search_aspects.length > 0 && (
            <ul className="mt-0.5 flex flex-wrap gap-1.5">
              {basis.search_aspects.map((aspect) => (
                <li
                  key={aspect}
                  className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground"
                >
                  {aspect}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      <Button
        size="sm"
        variant="ghost"
        className="w-fit -ml-2.5"
        render={<a href="/intake" />}
        nativeButton={false}
      >
        <Pencil aria-hidden className="size-3" />
        Projektidee bearbeiten
      </Button>
    </div>
  )
}
