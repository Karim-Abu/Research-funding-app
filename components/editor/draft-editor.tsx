"use client"

import * as React from "react"
import { Eye, Pencil } from "lucide-react"
import { Textarea } from "@/components/ui/textarea"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

interface DraftEditorProps {
  draftText: string
  onChange: (value: string) => void
}

/**
 * Isolated draft editor. Styled textarea + markdown preview toggle.
 * Kept deliberately simple so a richer editor (e.g. Tiptap) can be swapped in later.
 */
export function DraftEditor({ draftText, onChange }: DraftEditorProps) {
  const [preview, setPreview] = React.useState(false)

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-end">
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={() => setPreview((p) => !p)}
        >
          {preview ? (
            <Pencil data-icon="inline-start" />
          ) : (
            <Eye data-icon="inline-start" />
          )}
          {preview ? "Bearbeiten" : "Vorschau"}
        </Button>
      </div>

      {preview ? (
        <div
          className={cn(
            "min-h-[320px] rounded-md border border-border bg-card p-4 text-sm leading-relaxed text-foreground"
          )}
        >
          {draftText.split("\n").map((line, i) =>
            line.trim() === "" ? (
              <div key={i} className="h-3" />
            ) : (
              <p key={i} className="mb-3">
                {line}
              </p>
            )
          )}
        </div>
      ) : (
        <Textarea
          value={draftText}
          onChange={(e) => onChange(e.target.value)}
          placeholder="Beginnen Sie hier mit Ihrem Antragstext…"
          className="min-h-[320px] resize-y text-sm leading-relaxed"
        />
      )}
    </div>
  )
}
