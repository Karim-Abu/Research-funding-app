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
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { cn } from "@/lib/utils"
import {
  uploadSource,
  ApiError,
  BRIDGE_UNREACHABLE_MESSAGE,
} from "@/lib/api"
import { isMock } from "@/lib/app-mode"
import type { Source, SourceStatus, SourceType } from "@/lib/quellen-mock-data"

// Default (mock) accept list; live mode passes the contract-supported types.
const ALLOWED_EXTENSIONS = [".txt", ".md"]

function isAllowedFile(name: string, accept: string[]): boolean {
  const lower = name.toLowerCase()
  return accept.some((ext) => lower.endsWith(ext))
}

// ---------------------------------------------------------------------------
// Source status badge — neutral "technical state" styles (NOT approval colours)
// ---------------------------------------------------------------------------

const SOURCE_STATUS_CONFIG: Record<
  SourceStatus,
  { label: string; className: string; icon: React.ElementType }
> = {
  uploaded: {
    label: "Hochgeladen",
    className: "bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300",
    icon: Loader2,
  },
  processing: {
    label: "In Verarbeitung",
    className: "bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300",
    icon: Loader2,
  },
  processed: {
    label: "Verarbeitet",
    className: "bg-muted text-muted-foreground",
    icon: CheckCircle2,
  },
  needs_manual_input: {
    label: "Manuelle Prüfung nötig",
    className: "bg-amber-50 text-amber-700 dark:bg-amber-950 dark:text-amber-300",
    icon: AlertTriangle,
  },
  failed: {
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
        className={cn(
          "size-3",
          (status === "processing" || status === "uploaded") && "animate-spin"
        )}
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
  DOCX: FileText,
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
  /** Erhält die ausgewählten/abgelegten Dateien (bereits gefiltert). */
  onFiles: (files: File[]) => void
  /** Anzahl abgelehnter Dateien (falscher Typ) beim letzten Versuch. */
  onRejected: (count: number) => void
  /** Erlaubte Dateiendungen (Default: .txt/.md). */
  accept?: string[]
}

function UploadZone({
  onFiles,
  onRejected,
  accept = ALLOWED_EXTENSIONS,
}: UploadZoneProps) {
  const [dragOver, setDragOver] = React.useState(false)
  const inputRef = React.useRef<HTMLInputElement>(null)

  function acceptFiles(list: FileList | null) {
    if (!list || list.length === 0) return
    const files = Array.from(list)
    const allowed = files.filter((f) => isAllowedFile(f.name, accept))
    const rejected = files.length - allowed.length
    onRejected(rejected)
    if (allowed.length > 0) onFiles(allowed)
  }

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
    acceptFiles(e.dataTransfer.files)
  }

  function openPicker() {
    inputRef.current?.click()
  }

  return (
    <div className="flex flex-col gap-3">
      <input
        ref={inputRef}
        type="file"
        accept={accept.join(",")}
        multiple
        className="hidden"
        onChange={(e) => {
          acceptFiles(e.target.files)
          e.target.value = ""
        }}
      />

      {/* Drop zone */}
      <div
        role="button"
        tabIndex={0}
        aria-label="Dateien hochladen oder hier ablegen"
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onKeyDown={(e) => e.key === "Enter" && openPicker()}
        onClick={openPicker}
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
            {`oder per Schaltfläche auswählen — erlaubt: ${accept.join(", ")}`}
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          type="button"
          onClick={(e) => {
            e.stopPropagation()
            openPicker()
          }}
        >
          Dateien wählen
        </Button>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Source table
// ---------------------------------------------------------------------------

interface SourceTableProps {
  sources: Source[]
  onRemove?: (id: string) => void
  /** Live mode: the page owns the list (polling); no local optimistic state. */
  controlled?: boolean
  /** Live upload handler — replaces the mock setTimeout demo path. */
  onUploadFiles?: (files: File[]) => Promise<void> | void
  /** Live delete handler. */
  onDeleteSource?: (id: string) => void
  /** Allowed upload extensions (Default: .txt/.md). */
  acceptExtensions?: string[]
}

export function SourceTable({
  sources,
  onRemove,
  controlled = false,
  onUploadFiles,
  onDeleteSource,
  acceptExtensions,
}: SourceTableProps) {
  const [confirmId, setConfirmId] = React.useState<string | null>(null)
  const [localSources, setLocalSources] = React.useState<Source[]>(sources)
  const [uploadError, setUploadError] = React.useState<string | null>(null)

  // Live mode shows the page-owned list; mock mode keeps local optimistic state.
  const displayed = controlled ? sources : localSources

  function handleRemoveConfirm() {
    if (!confirmId) return
    if (onDeleteSource) {
      onDeleteSource(confirmId)
    } else {
      setLocalSources((prev) => prev.filter((s) => s.id !== confirmId))
      onRemove?.(confirmId)
    }
    setConfirmId(null)
  }

  async function handleFiles(files: File[]) {
    setUploadError(null)
    if (onUploadFiles) {
      try {
        await onUploadFiles(files)
      } catch (e) {
        setUploadError(
          e instanceof Error ? e.message : BRIDGE_UNREACHABLE_MESSAGE
        )
      }
      return
    }
    for (const file of files) {
      try {
        const source = await uploadSource(file)
        setLocalSources((prev) => [source, ...prev])
        if (isMock("legacy")) {
          // Demo: Verarbeitung schliesst nach kurzer Zeit ab.
          setTimeout(() => {
            setLocalSources((prev) =>
              prev.map((s) =>
                s.id === source.id
                  ? { ...s, status: "processed" as const }
                  : s
              )
            )
          }, 1500)
        }
      } catch (e) {
        setUploadError(
          e instanceof ApiError ? e.message : BRIDGE_UNREACHABLE_MESSAGE
        )
      }
    }
  }

  function handleRejected(count: number) {
    setUploadError(
      count > 0
        ? "Beta: Es können nur .txt- und .md-Dateien hochgeladen werden."
        : null
    )
  }

  const pendingSource = displayed.find((s) => s.id === confirmId)

  return (
    <div className="flex flex-col gap-6">
      <UploadZone
        onFiles={handleFiles}
        onRejected={handleRejected}
        accept={acceptExtensions}
      />

      {uploadError && (
        <p
          role="alert"
          className="flex items-center gap-1.5 text-xs text-status-blocker"
        >
          <AlertTriangle className="size-3.5 shrink-0" />
          {uploadError}
        </p>
      )}

      {displayed.length === 0 ? (
        <p
          role="status"
          className="py-8 text-center text-sm text-muted-foreground"
        >
          Noch keine Quellen vorhanden.
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
          {displayed.map((source) => (
            <div key={source.id} className="flex flex-col">
              <div
                role="row"
                className={cn(
                  "grid grid-cols-[1fr_80px_110px_1fr_56px] items-center gap-x-4 px-4 py-3 text-sm",
                  "border-b border-border last:border-0",
                  (source.status === "failed" ||
                    source.status === "needs_manual_input") &&
                    "bg-status-blocker/5"
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

              {/* Error / manual-input hint row */}
              {(source.status === "failed" ||
                source.status === "needs_manual_input") &&
                source.errorHint && (
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
