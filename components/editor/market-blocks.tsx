"use client"

// Gemeinsame Darstellungsbausteine für den Markt- und Konkurrenzvergleich.
//
// Marktbild und Evidenzlücken wurden zuvor in drei Komponenten (Quellen-Sektion,
// Sheet, Editor-Rail) handgeschrieben — mit abweichenden Limits und Wortlauten.
// Hier steht jede Darstellung genau einmal; `MarketDisclosure` gibt allen
// Aufklappern der Marktflächen dieselbe Form (gleiches Muster wie
// `MarketComparisonBasis`).

import * as React from "react"
import { ChevronRight } from "lucide-react"

import { cn } from "@/lib/utils"
import type { MarketPicturePoint } from "@/lib/market-view"

/**
 * Der EINE Aufklapper der Marktflächen — Vergleichsbasis, Marktbild, unzulässige
 * Aussagen und die Lückenliste sahen zuvor jeweils anders aus (mal native
 * Dreiecks-Markierung, mal Rahmen, mal ohne). Native `<details>`, damit der
 * Inhalt auch zugeklappt im DOM bleibt (Seitensuche, Screenreader-Navigation).
 */
export function MarketDisclosure({
  summary,
  count,
  icon,
  tone = "default",
  defaultOpen = false,
  className,
  testId,
  children,
}: {
  summary: React.ReactNode
  /** Anzahl der Einträge dahinter — sagt zugeklappt, wie viel folgt. */
  count?: number
  icon?: React.ReactNode
  /** `blocked` = Sperrhinweis (rote Fläche), sonst neutral. */
  tone?: "default" | "blocked"
  defaultOpen?: boolean
  className?: string
  testId?: string
  children: React.ReactNode
}) {
  const blocked = tone === "blocked"
  return (
    <details
      data-testid={testId}
      open={defaultOpen}
      className={cn(
        "group rounded-md border px-3 py-2.5",
        blocked
          ? "border-destructive/25 bg-destructive/5"
          : "border-border bg-muted/20",
        className
      )}
    >
      <summary
        className={cn(
          "flex cursor-pointer list-none items-center gap-1.5 text-xs font-medium [&::-webkit-details-marker]:hidden",
          blocked ? "text-destructive" : "text-foreground"
        )}
      >
        <ChevronRight
          aria-hidden
          className={cn(
            "size-3.5 shrink-0 transition-transform group-open:rotate-90",
            blocked ? "text-destructive/70" : "text-muted-foreground"
          )}
        />
        {icon}
        <span className="min-w-0">{summary}</span>
        {typeof count === "number" && (
          <span className={blocked ? "text-destructive/70" : "text-muted-foreground"}>
            {` (${count})`}
          </span>
        )}
      </summary>
      <div className="mt-2.5 pl-5">{children}</div>
    </details>
  )
}

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
      // Feste Beschriftungsspalte: die Rubriken stehen auf einer Linie, statt
      // je nach Textlänge zu wandern.
      className="grid gap-x-4 gap-y-2 text-xs sm:grid-cols-[9.5rem_1fr]"
    >
      {shown.map((point) => (
        <React.Fragment key={point.label}>
          <dt className="font-medium text-muted-foreground">{point.label}</dt>
          <dd className="leading-relaxed text-foreground">{point.value}</dd>
        </React.Fragment>
      ))}
    </dl>
  )
}

/**
 * Offene Evidenzlücken — die Sätze kommen aus dem Backend und sind lang.
 * `collapsed` legt die ganze Liste hinter einen Aufklapper (Übersichtskarten:
 * die Anzahl genügt dort); sonst bleiben `limit` Einträge sichtbar und der Rest
 * liegt hinter einer Offenlegung. Nichts wird verschwiegen.
 */
export function MarketGapList({
  gaps,
  limit = 3,
  collapsed = false,
  label = "Offene Evidenzlücken",
  testId,
}: {
  gaps: string[]
  limit?: number
  /** Gesamte Liste hinter einem Aufklapper (Anzahl im Titel). */
  collapsed?: boolean
  /** `null`, wenn der Abschnittskopf der Fläche die Liste bereits benennt. */
  label?: string | null
  testId?: string
}) {
  if (gaps.length === 0) return null
  const bullets = (items: string[]) => (
    <ul className="list-disc space-y-1.5 pl-5 text-xs leading-relaxed text-muted-foreground">
      {items.map((gap) => (
        <li key={gap}>{gap}</li>
      ))}
    </ul>
  )

  if (collapsed) {
    return (
      <MarketDisclosure
        testId={testId}
        // Zwei Spans: der Titel bleibt als eigener Textknoten prüfbar.
        summary={<span>{label}</span>}
        count={gaps.length}
      >
        {bullets(gaps)}
      </MarketDisclosure>
    )
  }

  const visible = gaps.slice(0, limit)
  const hidden = gaps.slice(limit)
  return (
    <div data-testid={testId} className="flex flex-col gap-1.5">
      {label && <p className="text-xs font-medium text-foreground">{label}</p>}
      {bullets(visible)}
      {hidden.length > 0 && (
        <details className="group text-xs text-muted-foreground">
          <summary className="flex cursor-pointer list-none items-center gap-1.5 [&::-webkit-details-marker]:hidden">
            <ChevronRight
              aria-hidden
              className="size-3.5 shrink-0 transition-transform group-open:rotate-90"
            />
            {`Weitere ${hidden.length} Lücken anzeigen`}
          </summary>
          <div className="mt-1.5">{bullets(hidden)}</div>
        </details>
      )}
    </div>
  )
}
