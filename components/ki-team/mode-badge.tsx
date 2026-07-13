import { Sparkles, Ruler, Blend, UserRound, type LucideIcon } from "lucide-react"
import { cn } from "@/lib/utils"
import { MODE_LABELS } from "@/lib/ki-team-data"
import type { KiTeamRole, RoleMode } from "@/lib/ki-team-data"

// Lucide-Icons je Modus — immer zusammen mit Text bzw. sr-only-Label, nie Farbe
// allein (Barrierefreiheit). Ersetzt die früheren Geometrie-Glyphen ◆ ■ ●.
export const MODE_ICONS: Record<RoleMode, LucideIcon> = {
  ki: Sparkles,
  regelbasiert: Ruler,
  hybrid: Blend,
  mensch: UserRound,
}

// Farbtöne je Modus (bestehende Tokens): KI = primary/lila, regelbasiert =
// neutral, hybrid = subtil, Mensch = orange (= „Prüfung nötig / hier prüfen Sie").
const MODE_TINT: Record<RoleMode, string> = {
  ki: "border-primary/30 bg-primary/10 text-primary",
  regelbasiert: "border-border bg-muted text-foreground/70",
  hybrid: "border-primary/20 bg-primary/5 text-foreground/80",
  mensch: "border-status-partial/40 bg-status-partial/10 text-status-partial",
}

/** Nur die Akzentfarbe je Modus — für einfarbige Icons (z. B. Legende). */
export const MODE_ACCENT_TEXT: Record<RoleMode, string> = {
  ki: "text-primary",
  regelbasiert: "text-foreground/70",
  hybrid: "text-primary",
  mensch: "text-status-partial",
}

/** Vollständiges Badge (Icon + Text-Label) — Legende und Drawer-Kopf. */
export function ModeBadge({
  mode,
  className,
}: Readonly<{
  mode: RoleMode
  className?: string
}>) {
  const Icon = MODE_ICONS[mode]
  return (
    <span
      className={cn(
        "inline-flex h-6 w-fit shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full border px-2.5 text-xs font-medium",
        MODE_TINT[mode],
        className
      )}
    >
      <Icon aria-hidden="true" className="size-3.5" />
      {MODE_LABELS[mode]}
    </span>
  )
}

/**
 * Kompaktes Modus-Icon in getöntem Quadrat — führendes Zeichen der Rollenzeile.
 * Das Text-Label bleibt für Screenreader als sr-only erhalten (Legende erklärt
 * die Icons visuell).
 */
export function ModeIcon({
  mode,
  className,
}: Readonly<{
  mode: RoleMode
  className?: string
}>) {
  const Icon = MODE_ICONS[mode]
  return (
    <span
      className={cn(
        "inline-flex size-7 shrink-0 items-center justify-center rounded-md border",
        MODE_TINT[mode],
        className
      )}
    >
      <Icon aria-hidden="true" className="size-4" />
      <span className="sr-only">{MODE_LABELS[mode]}</span>
    </span>
  )
}

const STATUS_CHIP_CLASSES: Record<KiTeamRole["statusTone"], string> = {
  ready: "border-status-fulfilled/40 bg-status-fulfilled/10 text-status-fulfilled",
  active: "border-status-fulfilled/40 bg-status-fulfilled/10 text-status-fulfilled",
  demo: "border-border bg-muted text-muted-foreground",
  development: "border-status-partial/40 bg-status-partial/10 text-status-partial",
  none: "",
}

/**
 * Status-Chip — bewusst nur für „Demo-Modus" und „In Entwicklung" sichtbar.
 * „Bereit"/„Aktiv" bleiben unmarkiert, um Rauschen zu vermeiden (calm UI).
 */
export function StatusChip({
  role,
  className,
}: Readonly<{ role: KiTeamRole; className?: string }>) {
  if (
    role.statusTone === "none" ||
    role.statusTone === "ready" ||
    role.statusTone === "active" ||
    !role.statusLabel
  ) {
    return null
  }
  return (
    <span
      className={cn(
        "inline-flex h-5 w-fit shrink-0 items-center whitespace-nowrap rounded-full border px-2 py-0.5 text-xs font-medium",
        STATUS_CHIP_CLASSES[role.statusTone],
        className
      )}
    >
      {role.statusLabel}
    </span>
  )
}

/**
 * Hebt die Legende passende Karten hervor: Hybrid-Rollen zählen sowohl als
 * KI-gestützt als auch als regelbasiert.
 */
export function modeMatchesHighlight(
  mode: RoleMode,
  highlight: RoleMode | null
): boolean {
  if (highlight === null) return false
  if (mode === highlight) return true
  return mode === "hybrid" && (highlight === "ki" || highlight === "regelbasiert")
}
