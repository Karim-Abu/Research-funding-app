"use client"

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"

interface DiffConfirmDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  currentText: string
  suggestionText: string
  onConfirm: () => void
}

/** Two-column diff before a suggestion replaces existing draft text. */
export function DiffConfirmDialog({
  open,
  onOpenChange,
  currentText,
  suggestionText,
  onConfirm,
}: DiffConfirmDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle>Vorschlag übernehmen</DialogTitle>
          <DialogDescription>
            Vergleichen Sie den aktuellen Text mit dem Vorschlag, bevor Sie
            ersetzen.
          </DialogDescription>
        </DialogHeader>

        <div className="grid grid-cols-2 gap-4">
          <div className="flex flex-col gap-2">
            <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Aktueller Text
            </span>
            <ScrollArea className="h-64 rounded-md border border-border bg-muted/40 p-3">
              <p className="whitespace-pre-wrap text-sm leading-relaxed text-foreground">
                {currentText || "— (leer) —"}
              </p>
            </ScrollArea>
          </div>
          <div className="flex flex-col gap-2">
            <span className="text-xs font-semibold uppercase tracking-wide text-primary">
              Vorschlag
            </span>
            <ScrollArea className="h-64 rounded-md border border-primary/30 bg-primary/5 p-3">
              <p className="whitespace-pre-wrap text-sm leading-relaxed text-foreground">
                {suggestionText}
              </p>
            </ScrollArea>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Abbrechen
          </Button>
          <Button onClick={onConfirm}>Ersetzen bestätigen</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
