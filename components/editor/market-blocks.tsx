"use client"

// Gemeinsame Darstellungsbausteine für den Markt- und Konkurrenzvergleich.
//
// Marktbild und Evidenzlücken wurden zuvor in drei Komponenten (Quellen-Sektion,
// Sheet, Editor-Rail) handgeschrieben — mit abweichenden Limits und Wortlauten.
// Hier steht jede Darstellung genau einmal; `compact` unterscheidet Rail von den
// grossen Flächen (gleiches Muster wie `MarketComparisonBasis`).

import * as React from "react"
import type { MarketPicturePoint } from "@/lib/market-view"

export function MarketPictureList({
  points,
  limit,
  testId,
}: {
  points: MarketPicturePoint[]
  limit?: number
  testId?: string
}) {
  const shown = typeof limit === "number" ? points.slice(0, limit) : points
  if (shown.length === 0) return null
  return (
    <dl
      data-testid={testId}
      className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs"
    >
      {shown.map((point) => (
        <React.Fragment key={point.label}>
          <dt className="text-muted-foreground">{point.label}</dt>
          <dd className="text-foreground">{point.value}</dd>
        </React.Fragment>
      ))}
    </dl>
  )
}

/**
 * Offene Evidenzlücken — die Sätze kommen aus dem Backend und sind lang.
 * Sichtbar bleiben `limit` Einträge; der Rest liegt hinter einer Offenlegung,
 * damit die Liste eine Karte nicht dominiert. Nichts wird verschwiegen.
 */
export function MarketGapList({
  gaps,
  limit = 3,
  compact = false,
  testId,
}: {
  gaps: string[]
  limit?: number
  compact?: boolean
  testId?: string
}) {
  if (gaps.length === 0) return null
  const visible = gaps.slice(0, limit)
  const hidden = gaps.slice(limit)
  const size = compact ? "text-[11px]" : "text-xs"
  return (
    <div data-testid={testId} className={compact ? undefined : "mt-4"}>
      <p className={`font-medium text-foreground ${size}`}>Offene Evidenzlücken</p>
      <ul className={`mt-1 list-disc pl-5 text-muted-foreground ${size}`}>
        {visible.map((gap) => (
          <li key={gap}>{gap}</li>
        ))}
      </ul>
      {hidden.length > 0 && (
        <details className={`mt-1 text-muted-foreground ${size}`}>
          <summary className="cursor-pointer">
            {`Weitere ${hidden.length} Lücken anzeigen`}
          </summary>
          <ul className="mt-1 list-disc pl-5">
            {hidden.map((gap) => (
              <li key={gap}>{gap}</li>
            ))}
          </ul>
        </details>
      )}
    </div>
  )
}
