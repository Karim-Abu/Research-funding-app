"use client"

import { CheckCircle2, AlertTriangle, Circle, XCircle, UserCheck, FileX2, Search } from "lucide-react"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"
import {
  REQ_BUCKET_LABELS,
  REQ_BUCKET_STYLE,
  REQ_FILTER_LABELS,
  type ReqBucket,
  type ReqFilter,
  type ReqSummary,
} from "@/lib/requirements-view"

// ---------------------------------------------------------------------------
// Status badge (bucket-based) — "Erfüllt / Teilweise / Offen / Blocker"
// ---------------------------------------------------------------------------
const BUCKET_ICON: Record<ReqBucket, typeof CheckCircle2> = {
  fulfilled: CheckCircle2,
  partial: AlertTriangle,
  open: Circle,
  blocked: XCircle,
}

export function ReqBucketBadge({
  bucket,
  className,
}: {
  bucket: ReqBucket
  className?: string
}) {
  const Icon = BUCKET_ICON[bucket]
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium",
        REQ_BUCKET_STYLE[bucket].chip,
        className
      )}
    >
      <Icon className="size-3.5" />
      {REQ_BUCKET_LABELS[bucket]}
    </span>
  )
}

// ---------------------------------------------------------------------------
// Summary bar — calm count tiles, status colours used sparingly.
// ---------------------------------------------------------------------------
interface SummaryTile {
  label: string
  value: number
  icon: typeof CheckCircle2
  accent?: string
}

export function RequirementSummaryBar({ summary }: { summary: ReqSummary }) {
  const tiles: SummaryTile[] = [
    { label: "Erfüllt", value: summary.fulfilled, icon: CheckCircle2, accent: REQ_BUCKET_STYLE.fulfilled.text },
    { label: "Teilweise", value: summary.partial, icon: AlertTriangle, accent: REQ_BUCKET_STYLE.partial.text },
    { label: "Offen", value: summary.open, icon: Circle },
    { label: "Blocker", value: summary.blocked, icon: XCircle, accent: summary.blocked > 0 ? REQ_BUCKET_STYLE.blocked.text : undefined },
    { label: "Menschliche Prüfung nötig", value: summary.humanNeeded, icon: UserCheck, accent: summary.humanNeeded > 0 ? REQ_BUCKET_STYLE.partial.text : undefined },
    { label: "Ohne Beleg", value: summary.noEvidence, icon: FileX2 },
  ]

  return (
    <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
      {tiles.map((tile) => (
        <div
          key={tile.label}
          className="flex items-center gap-2.5 rounded-lg border border-border bg-card px-3 py-2.5"
        >
          <tile.icon
            className={cn("size-4 shrink-0 text-muted-foreground", tile.accent)}
            aria-hidden
          />
          <div className="flex min-w-0 flex-col">
            <dd className={cn("text-base font-semibold leading-none text-foreground", tile.accent)}>
              {tile.value}
            </dd>
            <dt className="mt-1 truncate text-[11px] leading-tight text-muted-foreground">
              {tile.label}
            </dt>
          </div>
        </div>
      ))}
    </dl>
  )
}

// ---------------------------------------------------------------------------
// Filter chips + search — frontend state only.
// ---------------------------------------------------------------------------
interface RequirementFilterBarProps {
  /** Filters to offer (besides "all"); pass only the ones that occur. */
  available: ReqFilter[]
  value: ReqFilter
  onChange: (value: ReqFilter) => void
  search: string
  onSearchChange: (value: string) => void
}

const FILTER_DISPLAY_ORDER: ReqFilter[] = [
  "blocked",
  "partial",
  "open",
  "human_needed",
  "no_evidence",
]

export function RequirementFilterBar({
  available,
  value,
  onChange,
  search,
  onSearchChange,
}: RequirementFilterBarProps) {
  const chips: ReqFilter[] = [
    "all",
    ...FILTER_DISPLAY_ORDER.filter((f) => available.includes(f)),
  ]

  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div className="flex flex-wrap gap-2" role="group" aria-label="Anforderungen filtern">
        {chips.map((chip) => {
          const active = value === chip
          return (
            <button
              key={chip}
              type="button"
              aria-pressed={active}
              onClick={() => onChange(chip)}
              className={cn(
                "inline-flex h-8 items-center rounded-full border px-3 text-xs font-medium transition-colors",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
                active
                  ? "border-primary bg-primary/10 text-primary"
                  : "border-border bg-card text-muted-foreground hover:bg-accent hover:text-accent-foreground"
              )}
            >
              {REQ_FILTER_LABELS[chip]}
            </button>
          )
        })}
      </div>
      <div className="relative w-full sm:w-64">
        <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder="Anforderung suchen…"
          className="h-9 pl-8"
          aria-label="Anforderung suchen"
        />
      </div>
    </div>
  )
}
