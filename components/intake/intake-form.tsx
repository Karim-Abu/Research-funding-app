"use client"

import * as React from "react"
import { useRouter } from "next/navigation"
import {
  Info,
  Trash2,
  CheckCircle2,
  Circle,
  XCircle,
  Loader2,
  FileUp,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { Alert } from "@/components/ui/alert"
import { Separator } from "@/components/ui/separator"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
} from "@/components/ui/select"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { DataClassBadge } from "@/components/status/data-class-badge"
import { cn } from "@/lib/utils"
import { flags } from "@/lib/flags"
import { saveIntake, setActiveProjectId } from "@/lib/intake-store"
import { createProjectFromIntake } from "@/lib/projects"
import { uploadFiles, UPLOAD_HINT_KEY } from "@/lib/sources"
import { useSession } from "@/components/providers/app-providers"
import type { DataClass, IntakeFormData } from "@/lib/types"

// ---------------------------------------------------------------------------
// Constants / static data
// ---------------------------------------------------------------------------

const INNOVATIONSFELDER = [
  "Digitalisierung & KI",
  "Medizintechnik & Life Sciences",
  "Energie & Umwelt",
  "Produktion & Materialien",
  "Mobilität & Transport",
  "Agrartechnologie",
  "Sonstiges",
]

const PROJEKTIDEE_MAX = 1200

// Erlaubte Upload-Formate — deckungsgleich mit der Quellen-Ingestion.
const ACCEPTED_EXTENSIONS = [".pdf", ".docx", ".txt"]

/** Neutrale, editierbare Beschreibung für Upload-first-Projekte (das Backend
 *  verlangt eine Beschreibung; sie kann später jederzeit ergänzt werden). */
export const INTAKE_DESCRIPTION_PLACEHOLDER =
  "Aus den hochgeladenen Unterlagen übernommen — Beschreibung folgt."

interface VertraulichkeitOption {
  value: DataClass
  title: string
  description: string
  ki: "möglich" | "nur mit Freigabe" | "nicht möglich"
  web: "möglich" | "bedingt möglich" | "nicht möglich"
}

const VERTRAULICHKEIT_OPTIONS: VertraulichkeitOption[] = [
  {
    value: "public",
    title: "Öffentlich",
    description: "Keine internen oder vertraulichen Informationen enthalten.",
    ki: "möglich",
    web: "möglich",
  },
  {
    value: "internal",
    title: "Intern",
    description: "Interne Informationen, nicht für die Öffentlichkeit bestimmt.",
    ki: "nur mit Freigabe",
    web: "bedingt möglich",
  },
  {
    value: "confidential",
    title: "Vertraulich",
    description:
      "Sensible Unternehmensdaten, nur für autorisierte Personen.",
    ki: "nicht möglich",
    web: "nicht möglich",
  },
  {
    value: "nda",
    title: "NDA / gesperrt",
    description:
      "Für NDA-geschützte oder rechtlich gesperrte Inhalte. Keine KI-Verarbeitung, keine Webrecherche, keine Browser-Zwischenspeicherung.",
    ki: "nicht möglich",
    web: "nicht möglich",
  },
]

const VERTRAULICHKEIT_SUMMARY: Record<DataClass, string> = {
  public:
    "Öffentlich gewählt: Externe KI-Dienste möglich, Webrecherche möglich.",
  internal:
    "Intern gewählt: Externe KI-Dienste nur mit Freigabe, Webrecherche bedingt möglich.",
  confidential:
    "Vertraulich gewählt: Verarbeitung nur lokal — keine externen KI-Dienste, keine Webrecherche.",
  nda: "NDA / gesperrt gewählt: Keine KI-Verarbeitung, keine Webrecherche, keine Browser-Zwischenspeicherung.",
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function isDirty(data: IntakeFormData, files: File[]): boolean {
  return (
    data.titel.trim() !== "" ||
    data.projektidee.trim() !== "" ||
    data.innovationsfeld !== "" ||
    files.length > 0 ||
    data.vertraulichkeit !== "confidential"
  )
}

/** Minimalangaben: eine Datei ODER (Titel UND Projektidee). Die
 *  Vertraulichkeit hat immer einen Wert (restriktiver Default). */
function isSubmitEnabled(data: IntakeFormData, files: File[]): boolean {
  return (
    files.length > 0 ||
    (data.titel.trim() !== "" && data.projektidee.trim() !== "")
  )
}

function hasAcceptedExtension(name: string): boolean {
  const lower = name.toLowerCase()
  return ACCEPTED_EXTENSIONS.some((ext) => lower.endsWith(ext))
}

function titleFromFilename(name: string): string {
  return name.replace(/\.[^.]+$/, "")
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function SectionHeading({
  title,
  subtitle,
}: {
  title: string
  subtitle: string
}) {
  return (
    <div className="flex flex-col gap-0.5">
      <h2 className="text-base font-semibold text-foreground">{title}</h2>
      <p className="text-sm text-muted-foreground">{subtitle}</p>
    </div>
  )
}

function FieldError({ message }: { message?: string }) {
  if (!message) return null
  return (
    <p role="alert" className="mt-1 text-xs text-destructive">
      {message}
    </p>
  )
}

function ConsequenceLine({
  label,
  value,
}: {
  label: string
  value: string
}) {
  const ok = value === "möglich"
  const conditional = value === "nur mit Freigabe" || value === "bedingt möglich"
  return (
    <span className="flex items-center gap-1.5 text-xs">
      {ok ? (
        <CheckCircle2 className="size-3.5 shrink-0 text-status-fulfilled" />
      ) : conditional ? (
        <Circle className="size-3.5 shrink-0 text-muted-foreground" />
      ) : (
        <XCircle className="size-3.5 shrink-0 text-muted-foreground" />
      )}
      <span className="text-muted-foreground">
        {label}:{" "}
        <span
          className={cn(
            "font-medium",
            ok ? "text-status-fulfilled" : "text-foreground"
          )}
        >
          {value}
        </span>
      </span>
    </span>
  )
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

interface IntakeFormErrors {
  titel?: string
  projektidee?: string
  dateien?: string
}

type SaveState = "idle" | "saving" | "error"

export function IntakeForm() {
  const router = useRouter()
  const { mode } = useSession()
  const [data, setData] = React.useState<IntakeFormData>({
    titel: "",
    projektidee: "",
    innovationsfeld: "",
    // Restriktiver Default (D2): nie eine leere Stufe, kein Kartenzwang.
    vertraulichkeit: "confidential",
  })
  // Ausgewählte Unterlagen bleiben bis zur Projektanlage nur im Speicher —
  // nie im Browser-Storage (R4.4).
  const [files, setFiles] = React.useState<File[]>([])
  const [errors, setErrors] = React.useState<IntakeFormErrors>({})
  const [saveState, setSaveState] = React.useState<SaveState>("idle")
  const [cancelDialogOpen, setCancelDialogOpen] = React.useState(false)
  const [classDialogOpen, setClassDialogOpen] = React.useState(false)
  const fileInputRef = React.useRef<HTMLInputElement>(null)
  // Ref for the scrollable content area — used to ensure page opens at top.
  const scrollRef = React.useRef<HTMLDivElement>(null)
  React.useEffect(() => {
    scrollRef.current?.scrollTo({ top: 0 })
  }, [])

  // -- field helpers --------------------------------------------------------

  function set<K extends keyof IntakeFormData>(key: K, value: IntakeFormData[K]) {
    setData((prev) => ({ ...prev, [key]: value }))
    // Clear the error for the field once the user edits it.
    if (key in errors) {
      setErrors((prev) => ({ ...prev, [key]: undefined }))
    }
  }

  // -- files ----------------------------------------------------------------

  function addFiles(list: FileList | File[]) {
    const incoming = Array.from(list)
    const rejected = incoming.filter((f) => !hasAcceptedExtension(f.name))
    const accepted = incoming.filter((f) => hasAcceptedExtension(f.name))
    setErrors((prev) => ({
      ...prev,
      dateien: rejected.length
        ? "Nicht unterstütztes Format. Erlaubt: PDF, DOCX, TXT."
        : undefined,
      titel: undefined,
      projektidee: undefined,
    }))
    if (accepted.length === 0) return
    setFiles((prev) => [...prev, ...accepted])
    // Upload-first: Titel aus dem ersten Dateinamen vorbelegen (editierbar).
    if (!data.titel.trim()) {
      set("titel", titleFromFilename(accepted[0].name))
    }
  }

  function removeFile(index: number) {
    setFiles((prev) => prev.filter((_, i) => i !== index))
  }

  const hasPdf = files.some((f) => f.name.toLowerCase().endsWith(".pdf"))

  // -- validation -----------------------------------------------------------

  function validate(): boolean {
    const next: IntakeFormErrors = {}
    if (files.length === 0) {
      if (!data.titel.trim()) {
        next.titel = "Bitte geben Sie einen Projekttitel ein."
      }
      if (!data.projektidee.trim()) {
        next.projektidee =
          "Bitte beschreiben Sie die Projektidee — oder laden Sie eine Datei hoch."
      }
    }
    setErrors(next)
    return Object.keys(next).length === 0
  }

  // -- submit / save --------------------------------------------------------

  /** Effektive Intake-Daten gemäss Matrix: Titel aus Dateiname ist bereits
   *  vorbelegt; leere Projektidee wird bei Upload-first durch die neutrale,
   *  später editierbare Platzhalter-Beschreibung ersetzt (Backend verlangt
   *  eine Beschreibung — bewusst kein Contract-Change). */
  function resolveIntake(): IntakeFormData {
    return {
      ...data,
      titel: data.titel.trim(),
      projektidee:
        data.projektidee.trim() ||
        (files.length > 0 ? INTAKE_DESCRIPTION_PLACEHOLDER : ""),
    }
  }

  /** Beide Aktionen erstellen das Projekt serverseitig (status «Entwurf») —
   *  «Später fortsetzen» ist echte Persistenz, kein Fake-Feedback. */
  async function handleCreate(destination: "weiter" | "home") {
    if (!validate()) return
    setSaveState("saving")
    const resolved = resolveIntake()
    // Session-Store: für nicht-public wird nur die Stufe gehalten (R4.4);
    // die Wahrheit liegt ab jetzt beim Server.
    saveIntake(resolved)
    try {
      const project = await createProjectFromIntake(resolved)
      setActiveProjectId(project.project_id)
      setSaveState("idle")

      // Unterlagen hochladen (nur live) — die Quelle erbt die Projektklasse
      // aus der Create-Antwort; die restriktivere Einstufung von Projekt und
      // Quelle setzt der Server durch (restrictive wins).
      if (mode === "live" && files.length > 0) {
        try {
          const docs = await uploadFiles(
            project.project_id,
            files,
            project.data_classification
          )
          if (destination === "home") {
            router.push("/")
            return
          }
          // Innolink-PDF: weiter zur Felderkennung (Import-Review übernimmt
          // Verarbeitung + Kandidaten; Übernahme bleibt einzeln und manuell).
          const firstPdf = docs.find((d) => d.type === "pdf")
          if (flags.innolinkImport && firstPdf) {
            router.push(
              `/import?source=${encodeURIComponent(firstPdf.source_id)}`
            )
            return
          }
          router.push("/quellen")
          return
        } catch {
          // Projekt ist gespeichert — Upload ehrlich als offen markieren.
          try {
            window.sessionStorage.setItem(UPLOAD_HINT_KEY, "1")
          } catch {
            // Storage blockiert — /quellen zeigt dann keinen Hinweis.
          }
          router.push("/quellen")
          return
        }
      }

      router.push(destination === "home" ? "/" : "/quellen")
    } catch {
      setSaveState("error")
    }
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    void handleCreate("weiter")
  }

  // -- cancel ---------------------------------------------------------------

  function handleCancelClick() {
    if (isDirty(data, files)) {
      setCancelDialogOpen(true)
    } else {
      router.push("/")
    }
  }

  // -------------------------------------------------------------------------

  const charCount = data.projektidee.length
  const submitEnabled = isSubmitEnabled(data, files)
  const saving = saveState === "saving"
  const dataClass: DataClass = data.vertraulichkeit || "confidential"

  // Konkrete Erklärung für den deaktivierten Zustand (nur fehlende Teile).
  const missingParts: string[] = []
  if (!data.titel.trim()) missingParts.push("Projekttitel")
  if (!data.projektidee.trim()) missingParts.push("kurze Projektidee")
  const missingHint =
    missingParts.length > 0
      ? `Noch offen: ${missingParts.join(" und ")} — oder laden Sie eine Datei hoch.`
      : null

  return (
    <>
      <form
        onSubmit={handleSubmit}
        noValidate
        className="flex min-h-full flex-col"
      >
        {/* Scrollable content area */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto">
          <div className="mx-auto w-full max-w-[720px] px-6 py-8">

            {/* Page header */}
            <div className="mb-8 flex flex-col gap-1">
              <h1 className="text-balance text-2xl font-semibold text-foreground">Projekt anlegen</h1>
              <p className="text-sm text-muted-foreground">
                Beschreiben Sie Ihre Projektidee, laden Sie vorhandene
                Unterlagen hoch oder kombinieren Sie beides.
              </p>
            </div>

            {/* Save error banner */}
            {saveState === "error" && (
              <Alert
                role="alert"
                className="mb-6 flex items-start gap-3 border-destructive/30 bg-destructive/5 text-sm text-foreground"
              >
                <XCircle className="mt-0.5 size-4 shrink-0 text-destructive" />
                <span>
                  Speichern fehlgeschlagen — Ihre Eingaben bleiben erhalten.{" "}
                  <button
                    type="submit"
                    className="font-medium underline underline-offset-2 hover:no-underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    Erneut versuchen
                  </button>
                </span>
              </Alert>
            )}

            <div className="flex flex-col gap-6">
              {/* Projekttitel */}
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="titel">Projekttitel</Label>
                <Input
                  id="titel"
                  value={data.titel}
                  onChange={(e) => set("titel", e.target.value)}
                  aria-invalid={!!errors.titel}
                  aria-describedby={errors.titel ? "titel-error" : undefined}
                  placeholder="z. B. KI-gestützte Materialentwicklung"
                  disabled={saving}
                />
                <FieldError message={errors.titel} />
              </div>

              {/* Projektidee */}
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="projektidee">Kurze Projektidee</Label>
                <p id="projektidee-hilfe" className="text-xs text-muted-foreground">
                  Beschreiben Sie kurz: Welches Problem wird gelöst? Was ist neu
                  gegenüber dem heutigen Stand? Wer nutzt die Lösung? Wenn Sie
                  Unterlagen hochladen, können Sie die Beschreibung auch später
                  ergänzen.
                </p>
                <Textarea
                  id="projektidee"
                  value={data.projektidee}
                  onChange={(e) => set("projektidee", e.target.value)}
                  maxLength={PROJEKTIDEE_MAX}
                  rows={5}
                  placeholder="z. B.: Problem — … · Neu daran — … · Nutzerinnen/Nutzer — … · Ergebnis — …"
                  aria-invalid={!!errors.projektidee}
                  aria-describedby="projektidee-hilfe projektidee-count"
                  disabled={saving}
                  className="resize-y"
                />
                <div
                  id="projektidee-count"
                  className={cn(
                    "flex justify-between text-xs",
                    charCount >= PROJEKTIDEE_MAX
                      ? "text-destructive"
                      : "text-muted-foreground"
                  )}
                >
                  <FieldError message={errors.projektidee} />
                  <span className="ml-auto tabular-nums">
                    {charCount} / {PROJEKTIDEE_MAX}
                  </span>
                </div>
              </div>

              {/* Innovationsfeld */}
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="innovationsfeld">Innovationsfeld</Label>
                <Select
                  value={data.innovationsfeld}
                  onValueChange={(v) => set("innovationsfeld", v ?? "")}
                  disabled={saving}
                >
                  <SelectTrigger id="innovationsfeld" className="w-full">
                    <span className={cn(!data.innovationsfeld && "text-muted-foreground")}>
                      {data.innovationsfeld || "Bitte wählen…"}
                    </span>
                  </SelectTrigger>
                  <SelectContent>
                    <SelectGroup>
                      {INNOVATIONSFELDER.map((f) => (
                        <SelectItem key={f} value={f}>
                          {f}
                        </SelectItem>
                      ))}
                    </SelectGroup>
                  </SelectContent>
                </Select>
              </div>

              {/* Kompakte Vertraulichkeit: restriktiver Default + «Ändern» */}
              <div className="flex flex-col gap-1.5">
                <Label>Vertraulichkeit der Daten</Label>
                <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-border bg-muted/40 px-3 py-2.5">
                  <div className="flex min-w-0 flex-col gap-1">
                    <DataClassBadge dataClass={dataClass} />
                    <span className="text-xs text-muted-foreground">
                      {VERTRAULICHKEIT_SUMMARY[dataClass]}
                    </span>
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    disabled={saving}
                    onClick={() => setClassDialogOpen(true)}
                  >
                    Ändern
                  </Button>
                </div>
              </div>

              {/* Unterlagen (optional) */}
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="intake-file-input">Unterlagen (optional)</Label>
                <p className="text-xs text-muted-foreground">
                  Innolink-Antrag (PDF) oder weitere Unterlagen. Neue Quellen
                  übernehmen die oben gewählte Vertraulichkeitsstufe.
                </p>
                <button
                  type="button"
                  disabled={saving}
                  onClick={() => fileInputRef.current?.click()}
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={(e) => {
                    e.preventDefault()
                    if (!saving) addFiles(e.dataTransfer.files)
                  }}
                  className={cn(
                    "flex flex-col items-center gap-2 rounded-lg border border-dashed border-border px-4 py-6 text-center transition-colors",
                    "outline-none hover:border-primary/40 hover:bg-accent/20 focus-visible:ring-2 focus-visible:ring-ring",
                    "disabled:pointer-events-none disabled:opacity-50"
                  )}
                >
                  <FileUp className="size-5 text-muted-foreground" aria-hidden />
                  <span className="text-sm text-foreground">
                    Datei auswählen oder hier ablegen
                  </span>
                  <span className="text-xs text-muted-foreground">
                    Erlaubt: PDF, DOCX, TXT
                  </span>
                </button>
                <input
                  ref={fileInputRef}
                  id="intake-file-input"
                  data-testid="intake-file-input"
                  type="file"
                  accept={ACCEPTED_EXTENSIONS.join(",")}
                  multiple
                  className="sr-only"
                  onChange={(e) => {
                    if (e.target.files) addFiles(e.target.files)
                    e.target.value = ""
                  }}
                />
                <FieldError message={errors.dateien} />
                {files.length > 0 && (
                  <ul className="flex flex-col gap-1.5">
                    {files.map((file, index) => (
                      <li
                        key={`${file.name}-${index}`}
                        className="flex items-center justify-between gap-2 rounded-md border border-border px-3 py-2"
                      >
                        <span className="min-w-0 truncate text-sm text-foreground">
                          {file.name}
                        </span>
                        <button
                          type="button"
                          onClick={() => removeFile(index)}
                          disabled={saving}
                          aria-label={`${file.name} entfernen`}
                          className="flex size-8 shrink-0 items-center justify-center rounded-md text-muted-foreground outline-none transition-colors hover:bg-destructive/10 hover:text-destructive focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50"
                        >
                          <Trash2 className="size-4" />
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
                {hasPdf && flags.innolinkImport && (
                  <p className="flex items-start gap-2 rounded-md bg-accent/40 px-3 py-2 text-xs text-foreground">
                    <Info className="mt-0.5 size-3.5 shrink-0 text-primary" />
                    <span>
                      Innolink-PDF erkannt: Nach dem Anlegen prüfen Sie die
                      erkannten Feldinhalte und übernehmen sie einzeln.
                    </span>
                  </p>
                )}
              </div>

              {/* Nicht-blockierender Hinweis statt Doppelerfassung */}
              <p className="text-xs text-muted-foreground">
                Partner und Budget ergänzen Sie im nächsten Schritt.
              </p>

              <Separator />

              {/* Förderprofil (read-only) */}
              <div className="flex flex-col gap-1.5">
                <div className="flex items-center gap-1.5">
                  <Label>Förderprofil</Label>
                  <Tooltip>
                    <TooltipTrigger
                      aria-label="Information zum Förderprofil"
                      className="inline-flex size-5 items-center justify-center rounded-full text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"
                    >
                      <Info className="size-3.5" />
                    </TooltipTrigger>
                    <TooltipContent side="right" className="max-w-[260px] text-xs">
                      Die Beta arbeitet mit einem Standard-Profil. Es bildet
                      nicht das vollständige Innosuisse-Portal ab.
                    </TooltipContent>
                  </Tooltip>
                </div>
                <div className="flex flex-col gap-0.5 rounded-md border border-border bg-muted/50 px-3 py-2 select-none">
                  <span className="text-sm text-foreground">
                    Innosuisse Innovationsprojekt mit Umsetzungspartner
                  </span>
                  <span className="text-xs text-muted-foreground">
                    Beta-Profil: unterstützt aktuell ausgewählte Portalfelder,
                    nicht das vollständige Innolink-Formular.
                  </span>
                </div>
              </div>
            </div>

            {/* Bottom padding so sticky footer doesn't overlap last content */}
            <div className="h-24" aria-hidden />
          </div>
        </div>

        {/* ── STICKY FOOTER ─────────────────────────────────────────── */}
        <div className="shrink-0 border-t border-border bg-card px-6 py-4">
          <div className="mx-auto flex w-full max-w-[720px] flex-wrap items-center justify-between gap-x-4 gap-y-2">
            <button
              type="button"
              onClick={handleCancelClick}
              disabled={saving}
              className="text-sm text-muted-foreground underline-offset-2 outline-none hover:text-foreground hover:underline focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50"
            >
              Abbrechen
            </button>

            {/* Erklärung des deaktivierten Zustands (Minimalangaben) */}
            {!submitEnabled && missingHint && (
              <p className="order-last w-full text-xs text-muted-foreground sm:order-none sm:w-auto sm:flex-1 sm:text-right">
                {missingHint}
              </p>
            )}

            <div className="flex items-center gap-3">
              <Button
                type="button"
                variant="outline"
                disabled={!submitEnabled || saving}
                onClick={() => void handleCreate("home")}
              >
                {saving && (
                  <Loader2
                    data-icon="inline-start"
                    className="animate-spin"
                  />
                )}
                Später fortsetzen
              </Button>

              <Button
                type="submit"
                disabled={!submitEnabled || saving}
              >
                {saving && (
                  <Loader2
                    data-icon="inline-start"
                    className="animate-spin"
                  />
                )}
                Projekt erstellen und weiter
              </Button>
            </div>
          </div>
        </div>
      </form>

      {/* Vertraulichkeit ändern */}
      <Dialog open={classDialogOpen} onOpenChange={setClassDialogOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Vertraulichkeit ändern</DialogTitle>
            <DialogDescription>
              Die Stufe bestimmt, welche Dienste genutzt werden dürfen. Die
              restriktivere Einstufung von Projekt und Quellen gilt.
            </DialogDescription>
          </DialogHeader>
          <RadioGroup
            value={dataClass}
            onValueChange={(v) => set("vertraulichkeit", v as DataClass)}
            className="flex flex-col gap-3"
          >
            {VERTRAULICHKEIT_OPTIONS.map((opt) => {
              const selected = dataClass === opt.value
              return (
                <label
                  key={opt.value}
                  htmlFor={`vtrl-${opt.value}`}
                  className={cn(
                    "flex cursor-pointer gap-3 rounded-lg border p-4 transition-colors",
                    selected
                      ? "border-primary bg-accent/40"
                      : "border-border hover:border-primary/40 hover:bg-accent/20"
                  )}
                >
                  <RadioGroupItem
                    id={`vtrl-${opt.value}`}
                    value={opt.value}
                    className="mt-0.5 shrink-0"
                  />
                  <div className="flex min-w-0 flex-col gap-1">
                    <span className="text-sm font-medium text-foreground">
                      {opt.title}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {opt.description}
                    </span>
                    <div className="mt-1 flex flex-col gap-1">
                      <ConsequenceLine
                        label="Externe KI-Dienste"
                        value={opt.ki}
                      />
                      <ConsequenceLine
                        label="Webrecherche"
                        value={opt.web}
                      />
                    </div>
                  </div>
                </label>
              )
            })}
          </RadioGroup>
          <DialogFooter>
            <Button onClick={() => setClassDialogOpen(false)}>Fertig</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Cancel confirmation dialog */}
      <Dialog open={cancelDialogOpen} onOpenChange={setCancelDialogOpen}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Änderungen verwerfen?</DialogTitle>
            <DialogDescription>
              Ungespeicherte Änderungen verwerfen?
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setCancelDialogOpen(false)}
            >
              Weiter bearbeiten
            </Button>
            <Button
              variant="destructive"
              onClick={() => {
                setCancelDialogOpen(false)
                router.push("/")
              }}
            >
              Verwerfen
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
