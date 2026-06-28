"use client"

import * as React from "react"
import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  CopyPlus,
  FileText,
  Info,
  Link2,
  Loader2,
  RefreshCw,
  Search,
  Trash2,
  Upload,
} from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import { cn } from "@/lib/utils"
import {
  importableSourceProjects,
  URL_SOURCE_KIND_LABELS,
  type ImportableSourceProject,
  type Source,
  type SourceStatus,
  type SourceType,
  type UrlSourceKind,
} from "@/lib/quellen-mock-data"

const DEFAULT_ACCEPT_EXTENSIONS = [".pdf", ".docx", ".txt", ".md"]

type TextSourceInput = {
  title: string
  text: string
}

type UrlSourceInput = {
  url: string
  kind: UrlSourceKind
}

type ImportSourceInput = {
  project: ImportableSourceProject
  sources: Source[]
}

interface SourceTableProps {
  sources: Source[]
  onRemove?: (id: string) => void
  /** Live mode: the page owns the list (polling); no local optimistic state. */
  controlled?: boolean
  /** Live upload handler. */
  onUploadFiles?: (files: File[]) => Promise<void> | void
  /** Live text-source handler. */
  onAddTextSource?: (input: TextSourceInput) => Promise<void> | void
  /** Live URL-source handler or frontend fallback provided by the page. */
  onAddUrlSource?: (input: UrlSourceInput) => Promise<void> | void
  /** MVP import handler or frontend fallback provided by the page. */
  onImportSources?: (input: ImportSourceInput) => Promise<void> | void
  /** Optional retry handler, only shown when available in controlled mode. */
  onRetrySource?: (source: Source) => Promise<void> | void
  /** Live delete handler. */
  onDeleteSource?: (id: string) => void
  /** Allowed upload extensions. */
  acceptExtensions?: string[]
  currentUserName?: string
  importProjects?: ImportableSourceProject[]
}

const SOURCE_STATUS_CONFIG: Record<
  SourceStatus,
  { label: string; className: string; icon: React.ElementType }
> = {
  uploaded: {
    label: "Ausstehend",
    className: "border-amber-200 bg-amber-50 text-amber-800",
    icon: Clock3,
  },
  processing: {
    label: "In Verarbeitung",
    className: "border-blue-200 bg-blue-50 text-blue-800",
    icon: Loader2,
  },
  processed: {
    label: "Verarbeitet",
    className: "border-status-fulfilled/20 bg-status-fulfilled/10 text-status-fulfilled",
    icon: CheckCircle2,
  },
  needs_manual_input: {
    label: "Prüfung nötig",
    className: "border-amber-200 bg-amber-50 text-amber-800",
    icon: AlertTriangle,
  },
  failed: {
    label: "Fehler",
    className: "border-destructive/20 bg-destructive/10 text-destructive",
    icon: AlertTriangle,
  },
}

const SOURCE_TYPE_ICON: Record<SourceType, React.ElementType> = {
  PDF: FileText,
  DOCX: FileText,
  URL: Link2,
  Text: FileText,
  Übernommen: CopyPlus,
}

const SOURCE_TYPE_LABEL: Record<SourceType, string> = {
  PDF: "PDF",
  DOCX: "Text",
  URL: "URL",
  Text: "Text",
  Übernommen: "Übernommen",
}

function sourceStatusLabel(status: SourceStatus): string {
  return SOURCE_STATUS_CONFIG[status].label
}

function SourceStatusBadge({ status }: { status: SourceStatus }) {
  const config = SOURCE_STATUS_CONFIG[status]
  const Icon = config.icon
  return (
    <Badge
      variant="outline"
      className={cn("gap-1 rounded-full px-2 py-0.5", config.className)}
    >
      <Icon
        className={cn(
          "size-3",
          status === "processing" && "animate-spin"
        )}
        aria-hidden
      />
      {config.label}
    </Badge>
  )
}

function SourceTypePill({ type }: { type: SourceType }) {
  const Icon = SOURCE_TYPE_ICON[type]
  return (
    <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
      <Icon className="size-3.5 shrink-0" aria-hidden />
      {SOURCE_TYPE_LABEL[type]}
    </span>
  )
}

function isAllowedFile(name: string, accept: string[]): boolean {
  const lower = name.toLowerCase()
  return accept.some((ext) => lower.endsWith(ext))
}

function fileTypeFromName(name: string): SourceType {
  const lower = name.toLowerCase()
  if (lower.endsWith(".pdf")) return "PDF"
  if (lower.endsWith(".docx")) return "DOCX"
  return "Text"
}

function acceptLabel(accept: string[]): string {
  return accept
    .map((ext) => ext.replace(".", "").toUpperCase())
    .join(", ")
}

function isProblemStatus(status: SourceStatus): boolean {
  return status === "failed" || status === "needs_manual_input"
}

function isValidPublicUrl(value: string): boolean {
  try {
    const url = new URL(value)
    return url.protocol === "https:" || url.protocol === "http:"
  } catch {
    return false
  }
}

function localId(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

export function SourceTable({
  sources,
  onRemove,
  controlled = false,
  onUploadFiles,
  onAddTextSource,
  onAddUrlSource,
  onImportSources,
  onRetrySource,
  onDeleteSource,
  acceptExtensions = DEFAULT_ACCEPT_EXTENSIONS,
  currentUserName = "Anna Keller",
  importProjects = importableSourceProjects,
}: SourceTableProps) {
  const fileInputRef = React.useRef<HTMLInputElement>(null)
  const [confirmId, setConfirmId] = React.useState<string | null>(null)
  const [detailsSource, setDetailsSource] = React.useState<Source | null>(null)
  const [localSources, setLocalSources] = React.useState<Source[]>(sources)
  const [uploadError, setUploadError] = React.useState<string | null>(null)
  const [textDialogOpen, setTextDialogOpen] = React.useState(false)
  const [urlDialogOpen, setUrlDialogOpen] = React.useState(false)
  const [importDialogOpen, setImportDialogOpen] = React.useState(false)

  React.useEffect(() => {
    if (!controlled) setLocalSources(sources)
  }, [controlled, sources])

  const displayed = controlled ? sources : localSources
  const pendingSource = displayed.find((source) => source.id === confirmId)

  function openFilePicker() {
    fileInputRef.current?.click()
  }

  function acceptFiles(list: FileList | null) {
    if (!list || list.length === 0) return
    const files = Array.from(list)
    const allowed = files.filter((file) =>
      isAllowedFile(file.name, acceptExtensions)
    )
    const rejected = files.length - allowed.length
    if (rejected > 0) {
      setUploadError(
        `Nicht unterstütztes Format. Bitte Format prüfen und erneut hochladen. Erlaubt: ${acceptLabel(
          acceptExtensions
        )}.`
      )
    } else {
      setUploadError(null)
    }
    if (allowed.length > 0) void handleFiles(allowed)
  }

  async function handleFiles(files: File[]) {
    setUploadError(null)
    if (onUploadFiles) {
      try {
        await onUploadFiles(files)
      } catch (error) {
        setUploadError(
          error instanceof Error
            ? `${error.message} Bitte Format prüfen oder erneut hochladen.`
            : "Die Datei konnte nicht übernommen werden. Bitte Format prüfen und erneut hochladen."
        )
      }
      return
    }

    const created = files.map<Source>((file) => ({
      id: localId("file"),
      name: file.name,
      type: fileTypeFromName(file.name),
      status: "processing",
      addedBy: currentUserName,
      addedAt: "soeben",
    }))
    setLocalSources((prev) => [...created, ...prev])
    setTimeout(() => {
      setLocalSources((prev) =>
        prev.map((source) =>
          created.some((item) => item.id === source.id)
            ? { ...source, status: "processed" as const }
            : source
        )
      )
    }, 1200)
  }

  function addLocalSources(next: Source[]) {
    setLocalSources((prev) => [...next, ...prev])
  }

  function handleRemoveConfirm() {
    if (!confirmId) return
    if (onDeleteSource) {
      onDeleteSource(confirmId)
    } else {
      setLocalSources((prev) => prev.filter((source) => source.id !== confirmId))
      onRemove?.(confirmId)
    }
    setConfirmId(null)
  }

  async function handleRetrySource(source: Source) {
    if (onRetrySource) {
      await onRetrySource(source)
      return
    }
    if (controlled) return
    setLocalSources((prev) =>
      prev.map((item) =>
        item.id === source.id ? { ...item, status: "processing" } : item
      )
    )
    setTimeout(() => {
      setLocalSources((prev) =>
        prev.map((item) =>
          item.id === source.id
            ? { ...item, status: "processed" as const, errorHint: undefined }
            : item
        )
      )
    }, 1200)
  }

  return (
    <div className="flex flex-col gap-6">
      <input
        ref={fileInputRef}
        type="file"
        accept={acceptExtensions.join(",")}
        multiple
        className="hidden"
        onChange={(event) => {
          acceptFiles(event.target.files)
          event.target.value = ""
        }}
      />

      <section
        aria-labelledby="source-ways-heading"
        className="rounded-lg border border-border bg-card p-4"
      >
        <div className="mb-4 flex flex-col gap-1">
          <h2 id="source-ways-heading" className="text-sm font-semibold">
            Quellen hinzufügen
          </h2>
          <p className="text-xs text-muted-foreground">
            Wählen Sie den passenden Weg für Ihre Unterlagen.
          </p>
        </div>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <FileSourceWayCard
            acceptExtensions={acceptExtensions}
            onFiles={acceptFiles}
            onOpenPicker={openFilePicker}
          />
          <SourceWayCard
            icon={Link2}
            title="URL hinzufügen"
            description="Webseite, PDF, FAQ oder Richtlinie als Quelle vormerken."
            actionLabel="URL hinzufügen"
            onClick={() => setUrlDialogOpen(true)}
          />
          <SourceWayCard
            icon={FileText}
            title="Text einfügen"
            description="Notizen, Gesprächsprotokolle oder Auszüge direkt erfassen."
            actionLabel="Text einfügen"
            onClick={() => setTextDialogOpen(true)}
          />
          <SourceWayCard
            icon={CopyPlus}
            title="Aus anderem Projekt übernehmen"
            description="Geeignete Beispielquellen aus vorhandenen Projekten übernehmen."
            actionLabel="Quellen übernehmen"
            onClick={() => setImportDialogOpen(true)}
          />
        </div>
      </section>

      {uploadError && (
        <div
          role="alert"
          className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-destructive/20 bg-destructive/5 px-4 py-3"
        >
          <p className="flex items-center gap-2 text-sm text-foreground">
            <AlertTriangle className="size-4 shrink-0 text-destructive" />
            {uploadError}
          </p>
          <Button type="button" variant="outline" size="sm" onClick={openFilePicker}>
            Erneut hochladen
          </Button>
        </div>
      )}

      {displayed.length === 0 ? (
        <p
          role="status"
          className="rounded-lg border border-dashed border-border bg-muted/20 py-10 text-center text-sm text-muted-foreground"
        >
          Noch keine Quellen vorhanden.
        </p>
      ) : (
        <SourceList
          sources={displayed}
          canRetry={Boolean(onRetrySource) || !controlled}
          onDetails={setDetailsSource}
          onDelete={(id) => setConfirmId(id)}
          onRetry={handleRetrySource}
          onReupload={openFilePicker}
        />
      )}

      <UrlSourceDialog
        open={urlDialogOpen}
        onOpenChange={setUrlDialogOpen}
        onAdd={async (input) => {
          if (onAddUrlSource) {
            await onAddUrlSource(input)
            return
          }
          addLocalSources([
            {
              id: localId("url"),
              name: input.url,
              type: "URL",
              status: "uploaded",
              addedBy: currentUserName,
              addedAt: "soeben",
              note: `${URL_SOURCE_KIND_LABELS[input.kind]} · Verarbeitung ausstehend.`,
            },
          ])
        }}
      />

      <TextSourceDialog
        open={textDialogOpen}
        onOpenChange={setTextDialogOpen}
        onAdd={async (input) => {
          if (onAddTextSource) {
            await onAddTextSource(input)
            return
          }
          addLocalSources([
            {
              id: localId("text"),
              name: input.title,
              type: "Text",
              status: "processed",
              addedBy: currentUserName,
              addedAt: "soeben",
              note: "Direkt eingefügter Text.",
            },
          ])
        }}
      />

      <ImportSourcesDialog
        open={importDialogOpen}
        onOpenChange={setImportDialogOpen}
        projects={importProjects}
        onImport={async (input) => {
          if (onImportSources) {
            await onImportSources(input)
            return
          }
          addLocalSources(
            input.sources.map((source) => ({
              ...source,
              id: localId("import"),
              type: "Übernommen" as const,
              status: "uploaded" as const,
              addedBy: currentUserName,
              addedAt: "soeben",
              note: `Aus „${input.project.title}“ übernommen. Verarbeitung ausstehend.`,
            }))
          )
        }}
      />

      <SourceDetailsDialog
        source={detailsSource}
        onOpenChange={(open) => {
          if (!open) setDetailsSource(null)
        }}
      />

      <Dialog
        open={Boolean(confirmId)}
        onOpenChange={(open) => !open && setConfirmId(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Quelle entfernen?</DialogTitle>
            <DialogDescription>
              {pendingSource
                ? `„${pendingSource.name}“ wird aus der Quellliste entfernt.`
                : "Die Quelle wird entfernt."}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmId(null)}>
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

function FileSourceWayCard({
  acceptExtensions,
  onFiles,
  onOpenPicker,
}: {
  acceptExtensions: string[]
  onFiles: (files: FileList | null) => void
  onOpenPicker: () => void
}) {
  const [dragOver, setDragOver] = React.useState(false)

  return (
    <div
      role="button"
      tabIndex={0}
      aria-label="Datei hochladen"
      onClick={onOpenPicker}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") onOpenPicker()
      }}
      onDragOver={(event) => {
        event.preventDefault()
        setDragOver(true)
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(event) => {
        event.preventDefault()
        setDragOver(false)
        onFiles(event.dataTransfer.files)
      }}
      className={cn(
        "flex min-h-40 cursor-pointer flex-col justify-between rounded-lg border p-4 text-left transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
        dragOver
          ? "border-primary bg-primary/5"
          : "border-border bg-background hover:bg-muted/30"
      )}
    >
      <div className="flex flex-col gap-2">
        <span className="flex size-9 items-center justify-center rounded-md bg-muted text-muted-foreground">
          <Upload className="size-4" aria-hidden />
        </span>
        <div>
          <h3 className="text-sm font-semibold text-foreground">
            Datei hochladen
          </h3>
          <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
            Datei auswählen oder hier ablegen. Erlaubt:{" "}
            {acceptLabel(acceptExtensions)}.
          </p>
        </div>
      </div>
      <Button
        type="button"
        variant="outline"
        size="sm"
        className="mt-4 w-fit"
        onClick={(event) => {
          event.stopPropagation()
          onOpenPicker()
        }}
      >
        Datei auswählen
      </Button>
    </div>
  )
}

function SourceWayCard({
  icon: Icon,
  title,
  description,
  actionLabel,
  onClick,
}: {
  icon: React.ElementType
  title: string
  description: string
  actionLabel: string
  onClick: () => void
}) {
  return (
    <div className="flex min-h-40 flex-col justify-between rounded-lg border border-border bg-background p-4">
      <div className="flex flex-col gap-2">
        <span className="flex size-9 items-center justify-center rounded-md bg-muted text-muted-foreground">
          <Icon className="size-4" aria-hidden />
        </span>
        <div>
          <h3 className="text-sm font-semibold text-foreground">{title}</h3>
          <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
            {description}
          </p>
        </div>
      </div>
      <Button
        type="button"
        variant="outline"
        size="sm"
        className="mt-4 w-fit"
        onClick={onClick}
      >
        {actionLabel}
      </Button>
    </div>
  )
}

function SourceList({
  sources,
  canRetry,
  onDetails,
  onDelete,
  onRetry,
  onReupload,
}: {
  sources: Source[]
  canRetry: boolean
  onDetails: (source: Source) => void
  onDelete: (id: string) => void
  onRetry: (source: Source) => void
  onReupload: () => void
}) {
  return (
    <section aria-labelledby="source-list-heading" className="flex flex-col gap-3">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h2 id="source-list-heading" className="text-sm font-semibold">
            Quellenliste
          </h2>
          <p className="text-xs text-muted-foreground">
            Status und nächste Schritte pro Quelle.
          </p>
        </div>
        <span className="text-xs text-muted-foreground">
          {sources.length} Quelle{sources.length === 1 ? "" : "n"}
        </span>
      </div>

      <div
        role="table"
        aria-label="Quellen"
        className="overflow-x-auto rounded-lg border border-border bg-card"
      >
        <div className="min-w-[920px]">
          <div
            role="row"
            className="grid grid-cols-[minmax(0,1.6fr)_100px_145px_150px_135px_190px] gap-x-4 border-b border-border bg-muted/40 px-4 py-2 text-xs font-medium uppercase tracking-wide text-muted-foreground"
          >
            <span role="columnheader">Name</span>
            <span role="columnheader">Typ</span>
            <span role="columnheader">Status</span>
            <span role="columnheader">Hinzugefügt von</span>
            <span role="columnheader">Hinzugefügt am</span>
            <span role="columnheader">Aktionen</span>
          </div>

          {sources.map((source) => (
            <div key={source.id} className="border-b border-border last:border-0">
              <div
                role="row"
                className={cn(
                  "grid grid-cols-[minmax(0,1.6fr)_100px_145px_150px_135px_190px] items-center gap-x-4 px-4 py-3 text-sm",
                  isProblemStatus(source.status) && "bg-destructive/5"
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
                <span role="cell" className="truncate text-xs text-muted-foreground">
                  {source.addedBy}
                </span>
                <span role="cell" className="text-xs text-muted-foreground">
                  {source.addedAt}
                </span>
                <span role="cell" className="flex items-center gap-1">
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-sm"
                    aria-label={`${source.name}: Details anzeigen`}
                    onClick={() => onDetails(source)}
                  >
                    <Info className="size-4" aria-hidden />
                  </Button>
                  {canRetry && isProblemStatus(source.status) && (
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon-sm"
                      aria-label={`${source.name}: Erneut verarbeiten`}
                      onClick={() => onRetry(source)}
                    >
                      <RefreshCw className="size-4" aria-hidden />
                    </Button>
                  )}
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-sm"
                    aria-label={`${source.name}: Löschen`}
                    onClick={() => onDelete(source.id)}
                  >
                    <Trash2 className="size-4" aria-hidden />
                  </Button>
                </span>
              </div>

              {isProblemStatus(source.status) && (
                <div className="border-t border-destructive/10 bg-destructive/5 px-4 py-3">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <p className="flex min-w-0 items-center gap-2 text-xs text-foreground">
                      <AlertTriangle className="size-3.5 shrink-0 text-destructive" />
                      <span className="truncate">
                        {source.errorHint ??
                          "Diese Quelle braucht Ihre Aufmerksamkeit."}
                      </span>
                    </p>
                    <div className="flex flex-wrap gap-2">
                      <Button
                        type="button"
                        variant="outline"
                        size="xs"
                        onClick={() => onDetails(source)}
                      >
                        <Search className="size-3" aria-hidden />
                        Format prüfen
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        size="xs"
                        onClick={onReupload}
                      >
                        <Upload className="size-3" aria-hidden />
                        Erneut hochladen
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        size="xs"
                        onClick={() => onDetails(source)}
                      >
                        Details anzeigen
                      </Button>
                      <Button
                        type="button"
                        variant="destructive"
                        size="xs"
                        onClick={() => onDelete(source.id)}
                      >
                        Quelle entfernen
                      </Button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

function UrlSourceDialog({
  open,
  onOpenChange,
  onAdd,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  onAdd: (input: UrlSourceInput) => Promise<void> | void
}) {
  const [url, setUrl] = React.useState("")
  const [kind, setKind] = React.useState<UrlSourceKind>("webpage")
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  async function submit() {
    const trimmed = url.trim()
    if (!isValidPublicUrl(trimmed)) {
      setError("Bitte eine gültige öffentliche HTTP- oder HTTPS-URL eingeben.")
      return
    }
    setBusy(true)
    setError(null)
    try {
      await onAdd({ url: trimmed, kind })
      setUrl("")
      setKind("webpage")
      onOpenChange(false)
    } catch (err) {
      setError(
        err instanceof Error
          ? `${err.message} Die URL wurde nicht hinzugefügt.`
          : "Die URL konnte nicht hinzugefügt werden."
      )
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>URL hinzufügen</DialogTitle>
          <DialogDescription>
            Erfassen Sie eine öffentliche Quelle. Automatisches Durchsuchen
            externer Webseiten ist in dieser Phase nicht Teil des MVP.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4">
          <div className="grid gap-1.5">
            <Label htmlFor="source-url">URL</Label>
            <Input
              id="source-url"
              value={url}
              onChange={(event) => setUrl(event.target.value)}
              placeholder="https://www.innosuisse.admin.ch/..."
              disabled={busy}
            />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="source-url-kind">Quellentyp</Label>
            <Select
              value={kind}
              onValueChange={(value) => {
                if (!value) return
                setKind(value as UrlSourceKind)
              }}
            >
              <SelectTrigger id="source-url-kind" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  {Object.entries(URL_SOURCE_KIND_LABELS).map(([value, label]) => (
                    <SelectItem key={value} value={value}>
                      {label}
                    </SelectItem>
                  ))}
                </SelectGroup>
              </SelectContent>
            </Select>
          </div>
          {error && (
            <p role="alert" className="text-sm text-destructive">
              {error}
            </p>
          )}
        </div>
        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={busy}
          >
            Abbrechen
          </Button>
          <Button
            type="button"
            onClick={submit}
            disabled={busy || !url.trim()}
          >
            {busy ? "Wird hinzugefügt..." : "Hinzufügen"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function TextSourceDialog({
  open,
  onOpenChange,
  onAdd,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  onAdd: (input: TextSourceInput) => Promise<void> | void
}) {
  const [title, setTitle] = React.useState("")
  const [text, setText] = React.useState("")
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  async function submit() {
    if (!title.trim() || !text.trim()) return
    setBusy(true)
    setError(null)
    try {
      await onAdd({ title: title.trim(), text })
      setTitle("")
      setText("")
      onOpenChange(false)
    } catch (err) {
      setError(
        err instanceof Error
          ? `${err.message} Der Text wurde nicht hinzugefügt.`
          : "Der Text konnte nicht hinzugefügt werden."
      )
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>Text einfügen</DialogTitle>
          <DialogDescription>
            Nutzen Sie diesen Weg für kurze Notizen, Auszüge oder
            Gesprächsprotokolle.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4">
          <div className="grid gap-1.5">
            <Label htmlFor="text-source-title">Titel der Quelle</Label>
            <Input
              id="text-source-title"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="z. B. Notiz Partnergespräch"
              disabled={busy}
            />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="text-source-content">Textinhalt</Label>
            <Textarea
              id="text-source-content"
              value={text}
              onChange={(event) => setText(event.target.value)}
              rows={8}
              placeholder="Text hier einfügen..."
              disabled={busy}
            />
          </div>
          {error && (
            <p role="alert" className="text-sm text-destructive">
              {error}
            </p>
          )}
        </div>
        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={busy}
          >
            Abbrechen
          </Button>
          <Button
            type="button"
            onClick={submit}
            disabled={busy || !title.trim() || !text.trim()}
          >
            {busy ? "Wird hinzugefügt..." : "Als Quelle hinzufügen"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function ImportSourcesDialog({
  open,
  onOpenChange,
  projects,
  onImport,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  projects: ImportableSourceProject[]
  onImport: (input: ImportSourceInput) => Promise<void> | void
}) {
  const firstProjectId = projects[0]?.id ?? ""
  const [projectId, setProjectId] = React.useState(firstProjectId)
  const [selectedIds, setSelectedIds] = React.useState<Set<string>>(new Set())
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  React.useEffect(() => {
    if (open) {
      setProjectId(firstProjectId)
      setSelectedIds(new Set())
      setError(null)
    }
  }, [open, firstProjectId])

  const project =
    projects.find((item) => item.id === projectId) ?? projects[0] ?? null
  const selectedSources =
    project?.sources.filter((source) => selectedIds.has(source.id)) ?? []

  function toggleSource(id: string, checked: boolean) {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (checked) next.add(id)
      else next.delete(id)
      return next
    })
  }

  async function submit() {
    if (!project || selectedSources.length === 0) return
    setBusy(true)
    setError(null)
    try {
      await onImport({ project, sources: selectedSources })
      onOpenChange(false)
    } catch (err) {
      setError(
        err instanceof Error
          ? `${err.message} Die Quellen wurden nicht übernommen.`
          : "Die Quellen konnten nicht übernommen werden."
      )
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>Aus anderem Projekt übernehmen</DialogTitle>
          <DialogDescription>
            Wählen Sie vorhandene Beispielquellen aus und übernehmen Sie sie in
            diesen Antrag.
          </DialogDescription>
        </DialogHeader>
        {project ? (
          <div className="grid gap-4">
            <div className="grid gap-1.5">
              <Label htmlFor="import-project">Projekt</Label>
              <Select
                value={project.id}
                onValueChange={(value) => {
                  if (!value) return
                  setProjectId(value)
                  setSelectedIds(new Set())
                }}
              >
                <SelectTrigger id="import-project" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    {projects.map((item) => (
                      <SelectItem key={item.id} value={item.id}>
                        {item.title}
                      </SelectItem>
                    ))}
                  </SelectGroup>
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              {project.sources.map((source) => (
                <label
                  key={source.id}
                  className="flex cursor-pointer items-start gap-3 rounded-lg border border-border p-3 hover:bg-muted/30"
                >
                  <Checkbox
                    checked={selectedIds.has(source.id)}
                    onCheckedChange={(checked) =>
                      toggleSource(source.id, checked === true)
                    }
                    className="mt-0.5"
                  />
                  <span className="flex min-w-0 flex-1 flex-col gap-1">
                    <span className="truncate text-sm font-medium text-foreground">
                      {source.name}
                    </span>
                    <span className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                      <SourceTypePill type={source.type} />
                      <span>{source.addedBy}</span>
                      <span>{source.addedAt}</span>
                    </span>
                  </span>
                </label>
              ))}
            </div>
            {error && (
              <p role="alert" className="text-sm text-destructive">
                {error}
              </p>
            )}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">
            Keine Beispielquellen verfügbar.
          </p>
        )}
        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={busy}
          >
            Abbrechen
          </Button>
          <Button
            type="button"
            onClick={submit}
            disabled={busy || selectedSources.length === 0}
          >
            {busy
              ? "Wird übernommen..."
              : "Ausgewählte Quellen übernehmen"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function SourceDetailsDialog({
  source,
  onOpenChange,
}: {
  source: Source | null
  onOpenChange: (open: boolean) => void
}) {
  return (
    <Dialog open={Boolean(source)} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Quelldetails</DialogTitle>
          <DialogDescription>
            Fachliche Informationen zur Quelle und empfohlene nächste Schritte.
          </DialogDescription>
        </DialogHeader>
        {source && (
          <div className="grid gap-4">
            <dl className="grid grid-cols-[130px_1fr] gap-x-4 gap-y-2 text-sm">
              <dt className="text-muted-foreground">Name</dt>
              <dd className="min-w-0 break-words text-foreground">
                {source.name}
              </dd>
              <dt className="text-muted-foreground">Typ</dt>
              <dd>
                <SourceTypePill type={source.type} />
              </dd>
              <dt className="text-muted-foreground">Status</dt>
              <dd>
                <SourceStatusBadge status={source.status} />
              </dd>
              <dt className="text-muted-foreground">Hinzugefügt von</dt>
              <dd>{source.addedBy}</dd>
              <dt className="text-muted-foreground">Hinzugefügt am</dt>
              <dd>{source.addedAt}</dd>
            </dl>

            {source.note && (
              <p className="rounded-lg border border-border bg-muted/30 px-3 py-2 text-sm text-muted-foreground">
                {source.note}
              </p>
            )}

            {isProblemStatus(source.status) && (
              <div className="rounded-lg border border-destructive/20 bg-destructive/5 px-3 py-3">
                <p className="text-sm font-medium text-foreground">
                  Empfohlene Schritte
                </p>
                <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-muted-foreground">
                  <li>Format und Lesbarkeit der Datei prüfen.</li>
                  <li>Quelle erneut hochladen oder als Text erfassen.</li>
                  <li>Quelle entfernen, falls sie nicht benötigt wird.</li>
                </ul>
                {source.errorHint && (
                  <p className="mt-3 text-sm text-destructive">
                    {source.errorHint}
                  </p>
                )}
              </div>
            )}
          </div>
        )}
        <DialogFooter>
          <Button type="button" onClick={() => onOpenChange(false)}>
            Schließen
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
