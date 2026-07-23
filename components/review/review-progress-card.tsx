"use client"

// Bearbeitungs- und Prüfstand — combined status card for the Qualitätsprüfung:
// a segmented SVG progress ring over the quality-check groups (honest
// denominator, never a success score) plus the six status values with their
// accessible help popovers. Replaces the former six-tile summary row without
// losing any information.
//
// Dataviz notes (validated): the three status tokens pass lightness/chroma/
// contrast checks; amber↔red are close under deuteranopia (ΔE 4.0), so color
// is never the only carrier — fixed segment order (green→amber→red from
// 12 o'clock), 2–3px surface gaps, and a legend with labels + counts in the
// same order carry the identity. The ring itself is aria-hidden; a full-text
// aria-label sits on its container.

import { Badge } from "@/components/ui/badge"
import { StatusHelp } from "@/components/status/status-help"
import { cn } from "@/lib/utils"
import type { AreaProgress } from "@/lib/check-status"
import {
  PROGRESS_CARD_HELP,
  REVIEW_PROGRESS_NOTE,
  REVIEW_TILE_HELP,
} from "@/lib/review-view"

// ---------------------------------------------------------------------------
// Segmented progress ring (pure SVG, no chart library).
// ---------------------------------------------------------------------------
export interface RingSegment {
  value: number
  /** Text color class; the segment strokes with currentColor. */
  className: string
}

export function ProgressRing({
  segments,
  total,
  centerValue,
  centerLabel,
  ariaLabel,
  size = 120,
  strokeWidth = 10,
}: {
  /** Ring segments in fixed display order (clockwise from 12 o'clock). */
  segments: RingSegment[]
  /** Denominator; segment values must not exceed it. */
  total: number
  /** Big center text, e.g. "5 / 8". */
  centerValue: string
  /** Small line under the center value, e.g. "Prüfbereiche bestanden". */
  centerLabel: string
  /** Full-text description for screen readers. */
  ariaLabel: string
  size?: number
  strokeWidth?: number
}) {
  const radius = (size - strokeWidth) / 2
  const circumference = 2 * Math.PI * radius
  const visible = segments.filter((s) => s.value > 0)
  // 2px surface gap between adjacent fills (only when >1 segment is shown).
  const gap = visible.length > 1 ? 3 : 0
  const usable = circumference - gap * visible.length
  const safeTotal = Math.max(total, 1)

  let offset = 0
  const arcs = visible.map((segment, index) => {
    const length = (segment.value / safeTotal) * usable
    const arc = { ...segment, length, start: offset, key: index }
    offset += length + gap
    return arc
  })

  return (
    <div
      role="img"
      aria-label={ariaLabel}
      className="relative flex shrink-0 items-center justify-center"
      style={{ width: size, height: size }}
    >
      <svg width={size} height={size} aria-hidden className="-rotate-90">
        {/* Track — recessive, one shade off the surface. */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          strokeWidth={strokeWidth}
          className="stroke-muted"
        />
        {arcs.map((arc) => (
          <circle
            key={arc.key}
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            strokeWidth={strokeWidth}
            stroke="currentColor"
            strokeDasharray={`${arc.length} ${circumference - arc.length}`}
            strokeDashoffset={-arc.start}
            className={arc.className}
          />
        ))}
      </svg>
      {/* Center text wears text tokens, never a series color. */}
      <div className="absolute inset-0 flex flex-col items-center justify-center px-3 text-center">
        <span className="text-xl font-semibold leading-none text-foreground">
          {centerValue}
        </span>
        <span className="mt-1 text-[10px] leading-tight text-muted-foreground">
          {centerLabel}
        </span>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Legend row — count + label + accessible help, optional ring color dot.
// ---------------------------------------------------------------------------
function LegendRow({
  label,
  value,
  help,
  dotClassName,
  accentClassName,
  displayValue,
}: {
  label: string
  value: number
  help: string
  /** Ring color dot (only for the three ring statuses). */
  dotClassName?: string
  /** Value accent, applied only when > 0 (mirrors the former tiles). */
  accentClassName?: string
  /** RUN 4A: ehrlicher Textwert statt Zahl (z. B. «Nicht geprüft» — nie 0). */
  displayValue?: string
}) {
  return (
    <div className="flex items-center gap-2 py-0.5">
      {dotClassName ? (
        <span
          aria-hidden
          className={cn("size-2 shrink-0 rounded-full", dotClassName)}
        />
      ) : (
        <span aria-hidden className="size-2 shrink-0" />
      )}
      <dt className="flex min-w-0 flex-1 items-center gap-1 text-xs text-muted-foreground">
        <span className="truncate">{label}</span>
        <StatusHelp label={label} text={help} />
      </dt>
      <dd
        className={cn(
          "text-sm font-semibold tabular-nums",
          displayValue ? "text-muted-foreground" : "text-foreground",
          !displayValue && value > 0 && accentClassName
        )}
      >
        {displayValue ?? value}
      </dd>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Card — Zahlen kommen ausschliesslich aus dem autoritativen Check-Status-View
// (Prüfbereiche) und der Fix Queue («Blockierende Aufgaben»/Evidenzhinweise).
// «Nicht geprüft» ist ein eigenes graues Segment — nie stillschweigend grün.
// ---------------------------------------------------------------------------
export function ReviewProgressCard({
  progress,
  blockingTasks,
  evidenceNotes,
  pruefungNoetig,
  missingMandatory = null,
  qualityRisks = null,
  recheckRequired = false,
}: {
  progress: AreaProgress
  /** Gruppierte handlungsrelevante Aufgaben mit Blocker-Severity. */
  blockingTasks: number
  /** Technische Zahl der einzelnen Evidenzhinweise (claimgenau). */
  evidenceNotes: number
  pruefungNoetig: number
  /** RUN 4A: offene Pflichtfeld-Befunde; null = Prüfung nicht ausgeführt. */
  missingMandatory?: number | null
  /** RUN 4A: offene Warnhinweise aller Bereiche; null = nicht ausgeführt. */
  qualityRisks?: number | null
  recheckRequired?: boolean
}) {
  const ariaLabel =
    `Bearbeitungs- und Prüfstand: ${progress.bestanden} von ${progress.total} ` +
    `Prüfbereichen bestanden, ${progress.teilweise} teilweise bestanden, ` +
    `${progress.nichtBestanden} nicht bestanden, ` +
    `${progress.nichtGeprueft} nicht geprüft.`

  return (
    <section
      data-testid="review-progress-card"
      className="flex flex-col gap-3 rounded-lg border border-border bg-card px-5 py-4"
    >
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="flex items-center gap-1.5 text-sm font-semibold text-foreground">
          Bearbeitungs- und Prüfstand
          <StatusHelp
            label="Bearbeitungs- und Prüfstand"
            text={PROGRESS_CARD_HELP}
          />
        </h2>
        {recheckRequired && (
          <Badge variant="outline" className="text-muted-foreground">
            Stand veraltet
          </Badge>
        )}
      </div>

      {/* Small screens: ring above the list; from sm: side by side. */}
      <div className="flex flex-col items-center gap-4 sm:flex-row sm:items-start sm:gap-6">
        <ProgressRing
          segments={[
            { value: progress.bestanden, className: "text-status-fulfilled" },
            { value: progress.teilweise, className: "text-status-partial" },
            { value: progress.nichtBestanden, className: "text-destructive" },
            { value: progress.nichtGeprueft, className: "text-muted-foreground/50" },
          ]}
          total={progress.total}
          centerValue={`${progress.bestanden} / ${progress.total}`}
          centerLabel="Prüfbereiche bestanden"
          ariaLabel={ariaLabel}
        />

        <dl className="w-full min-w-0 flex-1 self-center">
          {/* Block A — the four ring statuses (dots match the segments). */}
          <LegendRow
            label="Bestanden"
            value={progress.bestanden}
            help={REVIEW_TILE_HELP.bestanden}
            dotClassName="bg-status-fulfilled"
          />
          <LegendRow
            label="Teilweise bestanden"
            value={progress.teilweise}
            help={REVIEW_TILE_HELP.teilweise}
            dotClassName="bg-status-partial"
          />
          <LegendRow
            label="Nicht bestanden"
            value={progress.nichtBestanden}
            help={REVIEW_TILE_HELP.nichtBestanden}
            dotClassName="bg-destructive"
            accentClassName="text-destructive"
          />
          <LegendRow
            label="Nicht geprüft"
            value={progress.nichtGeprueft}
            help={REVIEW_TILE_HELP.nichtGeprueft}
            dotClassName="bg-muted-foreground/50"
          />

          {/* Block B — RUN 4A: die vier primären Kennzahlen. «Nicht geprüft»
              erscheint als Text, nie als Null-Ergebnis. */}
          <div className="my-2 border-t border-border" aria-hidden />
          <LegendRow
            label="Formale Blocker"
            value={blockingTasks}
            help={REVIEW_TILE_HELP.blockierendeAufgaben}
            accentClassName="text-destructive"
          />
          <LegendRow
            label="Fehlende Pflichtangaben"
            value={missingMandatory ?? 0}
            displayValue={missingMandatory === null ? "Nicht geprüft" : undefined}
            help={REVIEW_TILE_HELP.fehlendePflichtangaben}
            accentClassName="text-destructive"
          />
          <LegendRow
            label="Wichtige Qualitätsrisiken"
            value={qualityRisks ?? 0}
            displayValue={qualityRisks === null ? "Nicht geprüft" : undefined}
            help={REVIEW_TILE_HELP.qualitaetsrisiken}
            accentClassName="text-status-partial"
          />
          <LegendRow
            label="Offene menschliche Prüfungen"
            value={pruefungNoetig}
            help={REVIEW_TILE_HELP.pruefungNoetig}
            accentClassName="text-status-partial"
          />
        </dl>
      </div>

      <p className="text-xs text-muted-foreground">{REVIEW_PROGRESS_NOTE}</p>

      {/* RUN 4A: technische Claim-Zahl verlagert, nicht gelöscht. */}
      <details className="text-xs text-muted-foreground">
        <summary className="cursor-pointer">Technische Details</summary>
        <p className="mt-1">
          Unterliegende Evidenzhinweise (claimgenau): {evidenceNotes}. Sie
          blockieren nicht automatisch.
        </p>
      </details>
    </section>
  )
}
