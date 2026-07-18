"use client"

import { Sparkles } from "lucide-react"
import { Button } from "@/components/ui/button"
import type { ProcessingMode } from "@/lib/runs"

interface LiveRunBannerProps {
  /** Verarbeitungsmodus des aktuell aktiven (abgeschlossenen) Laufs. */
  processingMode: ProcessingMode
  /** Konkreter Grund, warum kein Live-Lauf möglich ist (Button deaktiviert). */
  disabledReason?: string | null
  onCreate: () => void
}

/**
 * Hinweis auf der Quellen-Seite: Der aktive Lauf ist kein Live-Lauf. Bietet
 * für öffentliche/anonymisierte Projekte die Primäraktion «Neuen Live-Lauf
 * erstellen» an — nie ein stiller Wechsel, der alte Lauf bleibt unverändert.
 */
export function LiveRunBanner({
  processingMode,
  disabledReason,
  onCreate,
}: LiveRunBannerProps) {
  const notice =
    processingMode === "deterministic_only"
      ? "Der aktive Lauf verwendet nur regelbasierte Verarbeitung."
      : "Der aktive Lauf verwendet keine Live-KI."
  return (
    <div
      role="status"
      className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-primary/30 bg-primary/5 px-4 py-3"
    >
      <div className="flex flex-col gap-0.5">
        <p className="text-sm font-medium text-foreground">{notice}</p>
        <p className="text-xs text-muted-foreground">
          Ein neuer Live-Lauf nutzt echte KI-Vorschläge nach Ihrer Bestätigung.
          Der bisherige Lauf bleibt unverändert als Auditspur erhalten.
        </p>
        {disabledReason && (
          <p className="text-xs text-muted-foreground">{disabledReason}</p>
        )}
      </div>
      <Button onClick={onCreate} disabled={Boolean(disabledReason)}>
        <Sparkles className="mr-1.5 size-4" />
        Neuen Live-Lauf erstellen
      </Button>
    </div>
  )
}
