"use client"

import * as React from "react"
import {
  Upload,
  Link2,
  FileText,
  Loader2,
  AlertTriangle,
  Trash2,
  CheckCircle2,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { cn } from "@/lib/utils"
import type { Source, SourceStatus, SourceType } from "@/lib/quellen-mock-data"

// ---------------------------------------------------------------------------
// Source status badge — neutral "technical state" styles (NOT approval colours)
// ---------------------------------------------------------------------------

const SOURCE_STATUS_CONFIG: Record<
  SourceStatus,
  { label: string; className: string; icon: React.ElementType }
> = {
  processed: {
    label: "Verarbeitet",
    className: "bg-muted text-muted-foreground",
    icon: CheckCircle2,
  },
  processing: {
    label: "In Verarbeitung",
    className: "bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300",
    icon: Loader2,
  },
  error: {
    label: "Fehler",
    className: "bg-status-blocker/10 text-status-blocker",
    icon: AlertTriangle,
  },
}

function SourceStatusBadge({ status }: { status: SourceStatus }) {
  const c = SOURCE_STATUS_CONFIG[status]
  const Icon = c.icon
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium",
        c.className
      )}
    >
      <Icon
        className={cn("size-3", status === "processing" && "animate-spin")}
      />
      {c.label}
    </span>
  )
}

// ---------------------------------------------------------------------------
// Source type pill
// ---------------------------------------------------------------------------

const SOURCE_TYPE_ICON: Record<SourceType, React.ElementType> = {
  PDF: FileText,
  URL: Link2,
  Text: FileText,
}

function SourceTypePill({ type }: { type: SourceType }) {
  const Icon = SOURCE_TYPE_ICON[type]
  return (
    <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
      <Icon className="size-3 shrink-0" />
      {type}
    </span>
  )
}

// ---------------------------------------------------------------------------
// Upload zone
// ---------------------------------------------------------------------------

interface UploadZoneProps {
  onFileSelect?: () => void
  onUrlAdd?: (url: string) => void
  onTextInsert?: () => void
}

function UploadZone({ onFileSelect, onUrlAdd, onTextInsert }: UploadZoneProps) {
  const [dragOver, setDragOver] = React.useState(false)
  const [urlValue, setUrlValue] = React.useState("")
  const [showUrlInput, setShowUrlInput] = React.useState(false)
  const [urlError, setUrlError] = React.useState<string | null>(null)

  function handleDragOver(e: React.DragEvent) {
    e.preventDefault()
    setDragOver(true)
  }
  function handleDragLeave() {
    setDragOver(false)
  }
  function handleDrop(e: React.DragEvent) {
    e.preventDefault()
    setDragOver(false)
    onFileSelect?.()
  }

  function handleUrlSubmit(e: React.FormEvent) {
    e.preventDefault()
    const trimmed = urlValue.trim()
    if (!trimmed) return
    // Simple URL reachability simulation: treat example.org as unreachable.
    if (trimmed.includes("example.org")) {
      setUrlError(
        "URL nicht erreichbar — bitte prüfen Sie die Adresse und versuchen Sie es erneut."
      )
      return
    }
    setUrlError(null)
    setUrlValue("")
    setShowUrlInput(false)
    onUrlAdd?.(trimmed)
  }

  return (
    <div className="flex flex-col gap-3">
      {/* Drop zone */}
      <div
        role="button"
        tabIndex={0}
        aria-label="Dateien hochladen oder hier ablegen"
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onKeyDown={(e) => e.key === "Enter" && onFileSelect?.()}
        onClick={onFileSelect}
        className={cn(
          "flex min-h-[120px] cursor-pointer flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed transition-colors",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
          dragOver
            ? "border-primary bg-primary/5"
            : "border-border bg-muted/20 hover:bg-muted/40"
        )}
      >
        <Upload className="size-6 text-muted-foreground" />
        <div className="text-center">
          <p className="text-sm font-medium text-foreground">
            Dateien hierher ziehen
          </p>
          <p className="text-xs text-muted-foreground">
            oder per Schaltfläche auswählen
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          type="button"
          onClick={(e) => {
            e.stopPropagation()
            onFileSelect?.()
          }}
        >
          Dateien wählen
        </Button>
      </div>

      {/* Inline URL input */}
      <div className="flex flex-wrap items-start gap-2">
        <Button
          variant="outline"
          size="sm"
          type="button"
          onClick={() => {
            setShowUrlInput((v) => !v)
            setUrlError(null)
          }}
        >
          <Link2 className="mr-1.5 size-3.5" />
          URL hinzufügen
        </Button>
        <Button
          variant="outline"
          size="sm"
          type="button"
          onClick={onTextInsert}
        >
          <FileText className="mr-1.5 size-3.5" />
          Text einfügen
        </Button>
      </div>

      {showUrlInput && (
        <form
          onSubmit={handleUrlSubmit}
          className="flex flex-col gap-2"
          aria-label="URL hinzufügen"
        >
          <div className="flex gap-2">
            <Input
              type="url"
              placeholder="https://…"
              value={urlValue}
              onChange={(e) => {
                setUrlValue(e.target.value)
                setUrlError(null)
              }}
              className={cn(urlError && "border-status-blocker")}
              aria-invalid={!!urlError}
              aria-describedby={urlError ? "url-error" : undefined}
              autoFocus
            />
            <Button type="submit" size="sm">
              Hinzufügen
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => {
                setShowUrlInput(false)
                setUrlError(null)
                setUrlValue("")
              }}
            >
              Abbrechen
            </Button>
          </div>
          {urlError && (
            <p
              id="url-error"
              role="alert"
              className="flex items-center gap-1.5 text-xs text-status-blocker"
            >
              <AlertTriangle className="size-3.5 shrink-0" />
              {urlError}
            </p>
          )}
        </form>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Source table
// ---------------------------------------------------------------------------

interface SourceTableProps {
  sources: Source[]
  onRemove?: (id: string) => void
}

export function SourceTable({ sources, onRemove }: SourceTableProps) {
  const [confirmId, setConfirmId] = React.useState<string | null>(null)
  const [localSources, setLocalSources] =
    React.useState<Source[]>(sources)

  function handleRemoveConfirm() {
    if (!confirmId) return
    setLocalSources((prev) => prev.filter((s) => s.id !== confirmId))
    onRemove?.(confirmId)
    setConfirmId(null)
  }

  const pendingSource = localSources.find((s) => s.id === confirmId)

  return (
    <div className="flex flex-col gap-6">
      <UploadZone />

      {localSources.length === 0 ? (
        <p
          role="status"
          className="py-8 text-center text-sm text-muted-foreground"
        >
          Noch keine Quellen. Laden Sie Dokumente hoch oder fügen Sie eine URL
          hinzu.
        </p>
      ) : (
        <div
          role="table"
          aria-label="Quelldokumente"
          className="overflow-hidden rounded-lg border border-border"
        >
          {/* Header */}
          <div
            role="row"
            className="grid grid-cols-[1fr_80px_110px_1fr_56px] gap-x-4 border-b border-border bg-muted/40 px-4 py-2 text-xs font-medium uppercase tracking-wide text-muted-foreground"
          >
            <span role="columnheader">Name</span>
            <span role="columnheader">Typ</span>
            <span role="columnheader">Status</span>
            <span role="columnheader">Hinzugefügt</span>
            <span role="columnheader" className="sr-only">
              Aktionen
            </span>
          </div>

          {/* Rows */}
          {localSources.map((source) => (
            <div key={source.id} className="flex flex-col">
              <div
                role="row"
                className={cn(
                  "grid grid-cols-[1fr_80px_110px_1fr_56px] items-center gap-x-4 px-4 py-3 text-sm",
                  "border-b border-border last:border-0",
                  source.status === "error" && "bg-status-blocker/5"
                )}
              >
                <span
                  role="cell"
                  className="truncate font-medium text-foreground"
                  title={source.name}
                >
                  {source.name}
                </span>
                <span role="cell">
                  <SourceTypePill type={source.type} />
                </span>
                <span role="cell">
                  <SourceStatusBadge status={source.status} />
                </span>
                <span role="cell" className="text-xs text-muted-foreground">
                  {source.addedBy} · {source.addedAt}
                </span>
                <span role="cell" className="flex justify-end">
                  <button
                    type="button"
                    onClick={() => setConfirmId(source.id)}
                    aria-label={`${source.name} entfernen`}
                    className={cn(
                      "flex size-[44px] items-center justify-center rounded text-muted-foreground",
                      "transition-colors hover:bg-muted hover:text-foreground",
                      "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    )}
                  >
                    <Trash2 className="size-4" />
                  </button>
                </span>
              </div>

              {/* Error hint row */}
              {source.status === "error" && source.errorHint && (
                <div
                  role="row"
                  className="border-b border-border bg-status-blocker/5 px-4 pb-3 last:border-0"
                >
                  <p
                    role="cell"
                    className="flex items-center gap-1.5 text-xs text-status-blocker"
                  >
                    <AlertTriangle className="size-3.5 shrink-0" />
                    {source.errorHint}
                  </p>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Remove confirm dialog */}
      <Dialog
        open={!!confirmId}
        onOpenChange={(open) => !open && setConfirmId(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Quelle entfernen?</DialogTitle>
            <DialogDescription>
              {pendingSource
                ? `„${pendingSource.name}" wird aus der Quellliste entfernt. Diese Aktion kann nicht rückgängig gemacht werden.`
                : "Die Quelle wird entfernt."}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setConfirmId(null)}
            >
              Abbrechen
            </Button>
            <Button variant="destructive" onClick={handleRemoveConfirm}>
              Entfernen
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
