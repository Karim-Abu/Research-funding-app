"use client"

import { cn } from "@/lib/utils"
import { kiTeamTexts } from "@/lib/ki-team-data"
import type { RoleMode } from "@/lib/ki-team-data"
import { MODE_ICONS, MODE_ACCENT_TEXT } from "./mode-badge"

interface LegendProps {
  highlight: RoleMode | null
  onHighlight: (mode: RoleMode | null) => void
}

/**
 * Interaktive Legende: Hover/Fokus auf einem Eintrag hebt die passenden
 * Rollenzeilen im Phasenband hervor. Icon + Text, nie Farbe allein.
 */
export function Legend({ highlight, onHighlight }: Readonly<LegendProps>) {
  return (
    <ul className="flex flex-wrap gap-2" aria-label="Legende">
      {kiTeamTexts.legende.map((item) => {
        const Icon = MODE_ICONS[item.mode]
        const active = highlight === item.mode
        return (
          <li key={item.mode}>
            <button
              type="button"
              onMouseEnter={() => onHighlight(item.mode)}
              onMouseLeave={() => onHighlight(null)}
              onFocus={() => onHighlight(item.mode)}
              onBlur={() => onHighlight(null)}
              aria-label={`${item.text} — passende Rollen hervorheben`}
              className={cn(
                "flex cursor-default items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium outline-none transition-colors",
                "focus-visible:ring-2 focus-visible:ring-ring",
                active
                  ? "border-primary/40 bg-muted text-foreground"
                  : "border-border bg-card text-muted-foreground hover:text-foreground"
              )}
            >
              <Icon
                aria-hidden="true"
                className={cn("size-3.5", MODE_ACCENT_TEXT[item.mode])}
              />
              {item.text}
            </button>
          </li>
        )
      })}
    </ul>
  )
}
