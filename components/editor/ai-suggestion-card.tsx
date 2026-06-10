"use client"

import { FileText } from "lucide-react"
import { Card, CardContent, CardFooter } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import type { AISuggestion } from "@/lib/editor-data"

interface AISuggestionCardProps {
  suggestion: AISuggestion
  onAccept: (suggestion: AISuggestion) => void
  onAdjust: (suggestion: AISuggestion) => void
  onRegenerate: (suggestion: AISuggestion) => void
}

export function AISuggestionCard({
  suggestion,
  onAccept,
  onAdjust,
  onRegenerate,
}: AISuggestionCardProps) {
  return (
    <Card>
      <CardContent className="flex flex-col gap-3 pt-6">
        <div className="flex flex-col gap-2">
          {suggestion.text.map((p, i) => (
            <p key={i} className="text-sm leading-relaxed text-foreground">
              {p}
            </p>
          ))}
        </div>
        <div className="flex flex-wrap gap-1.5">
          {suggestion.evidence.map((chip) => (
            <span
              key={chip.label}
              className="inline-flex items-center gap-1 rounded-md bg-accent px-2 py-0.5 text-xs font-medium text-accent-foreground"
            >
              <FileText className="size-3" />
              {chip.label}
            </span>
          ))}
        </div>
      </CardContent>
      <CardFooter className="flex gap-2">
        <Button size="sm" onClick={() => onAccept(suggestion)}>
          Übernehmen
        </Button>
        <Button size="sm" variant="outline" onClick={() => onAdjust(suggestion)}>
          Anpassen
        </Button>
        <Button
          size="sm"
          variant="ghost"
          onClick={() => onRegenerate(suggestion)}
        >
          Neu erstellen
        </Button>
      </CardFooter>
    </Card>
  )
}
