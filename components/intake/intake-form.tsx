"use client"

import * as React from "react"
import { useRouter } from "next/navigation"
import {
  Info,
  Plus,
  Trash2,
  CheckCircle2,
  XCircle,
  Loader2,
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
import { cn } from "@/lib/utils"
import { saveIntake } from "@/lib/intake-store"
import type { DataClass, IntakeFormData, IntakePartner } from "@/lib/types"

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

interface VertraulichkeitOption {
  value: DataClass
  title: string
  description: string
  ki: "möglich" | "nicht möglich"
  web: "möglich" | "nicht möglich"
}

const VERTRAULICHKEIT_OPTIONS: VertraulichkeitOption[] = [
  {
    value: "public_synthetic",
    title: "Öffentlich (synthetisch)",
    description: "Keine unternehmensinternen Informationen enthalten.",
    ki: "möglich",
    web: "nicht möglich",
  },
  {
    value: "public_external",
    title: "Öffentlich (extern)",
    description: "Öffentlich zugängliche Informationen, keine Interna.",
    ki: "möglich",
    web: "möglich",
  },
  {
    value: "internal",
    title: "Intern",
    description: "Interne Informationen, nicht für die Öffentlichkeit bestimmt.",
    ki: "nicht möglich",
    web: "nicht möglich",
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
    title: "NDA",
    description: "Durch Geheimhaltungsvereinbarung geschützte Informationen.",
    ki: "nicht möglich",
    web: "nicht möglich",
  },
]

const VERTRAULICHKEIT_SUMMARY: Record<DataClass, string> = {
  public_synthetic:
    "Öffentlich (synthetisch) gewählt: Externe KI-Dienste möglich, Webrecherche nicht möglich.",
  public_external:
    "Öffentlich (extern) gewählt: Externe KI-Dienste möglich, Webrecherche möglich.",
  internal:
    "Intern gewählt: Verarbeitung nur lokal — keine externen KI-Dienste, keine Webrecherche.",
  confidential:
    "Vertraulich gewählt: Verarbeitung nur lokal — keine externen KI-Dienste, keine Webrecherche.",
  nda: "NDA gewählt: Verarbeitung nur lokal — keine externen KI-Dienste, keine Webrecherche.",
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function newPartner(): IntakePartner {
  return { id: crypto.randomUUID(), name: "", type: "Forschungspartner" }
}

function isDirty(data: IntakeFormData): boolean {
  return (
    data.titel.trim() !== "" ||
    data.projektidee.trim() !== "" ||
    data.innovationsfeld !== "" ||
    data.budgetrahmen.trim() !== "" ||
    data.vertraulichkeit !== "" ||
    data.partner.some((p) => p.name.trim() !== "")
  )
}

function isSubmitEnabled(data: IntakeFormData): boolean {
  return (
    data.titel.trim() !== "" &&
    data.projektidee.trim() !== "" &&
    data.vertraulichkeit !== ""
  )
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
  return (
    <span className="flex items-center gap-1.5 text-xs">
      {ok ? (
        <CheckCircle2 className="size-3.5 shrink-0 text-status-fulfilled" />
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
  budgetrahmen?: string
  vertraulichkeit?: string
}

type SaveState = "idle" | "saving" | "error"

export function IntakeForm() {
  const router = useRouter()
  const [data, setData] = React.useState<IntakeFormData>({
    titel: "",
    projektidee: "",
    innovationsfeld: "",
    budgetrahmen: "",
    vertraulichkeit: "",
    partner: [],
  })
  const [errors, setErrors] = React.useState<IntakeFormErrors>({})
  const [saveState, setSaveState] = React.useState<SaveState>("idle")
  const [cancelDialogOpen, setCancelDialogOpen] = React.useState(false)
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

  // -- partner list ---------------------------------------------------------

  function addPartner() {
    setData((prev) => ({ ...prev, partner: [...prev.partner, newPartner()] }))
  }

  function removePartner(id: string) {
    setData((prev) => ({
      ...prev,
      partner: prev.partner.filter((p) => p.id !== id),
    }))
  }

  function updatePartner(id: string, patch: Partial<Omit<IntakePartner, "id">>) {
    setData((prev) => ({
      ...prev,
      partner: prev.partner.map((p) => (p.id === id ? { ...p, ...patch } : p)),
    }))
  }

  // -- validation -----------------------------------------------------------

  function validate(): boolean {
    const next: IntakeFormErrors = {}
    if (!data.titel.trim()) {
      next.titel = "Bitte geben Sie einen Antragstitel ein."
    }
    if (!data.projektidee.trim()) {
      next.projektidee = "Bitte beschreiben Sie die Projektidee."
    }
    if (!data.vertraulichkeit) {
      next.vertraulichkeit = "Bitte wählen Sie eine Vertraulichkeitsstufe."
    }
    if (data.budgetrahmen && !/^\d+([.,]\d+)?$/.test(data.budgetrahmen.trim())) {
      next.budgetrahmen = "Bitte geben Sie einen gültigen Betrag ein (nur Zahlen)."
    }
    setErrors(next)
    return Object.keys(next).length === 0
  }

  // -- submit / save --------------------------------------------------------

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!validate()) return
    setSaveState("saving")
    // Simulate async save — prototype only, no real call.
    await new Promise((r) => setTimeout(r, 1200))
    setSaveState("idle")
    // Beta: Projektdaten in der Session halten; /quellen baut daraus den
    // Run-Start-Payload (POST /runs erhält intake + settings + Datenklasse).
    saveIntake(data)
    router.push("/quellen")
  }

  async function handleDraftSave() {
    setSaveState("saving")
    await new Promise((r) => setTimeout(r, 800))
    setSaveState("idle")
  }

  // -- cancel ---------------------------------------------------------------

  function handleCancelClick() {
    if (isDirty(data)) {
      setCancelDialogOpen(true)
    } else {
      router.push("/")
    }
  }

  // -------------------------------------------------------------------------

  const charCount = data.projektidee.length
  const submitEnabled = isSubmitEnabled(data)
  const saving = saveState === "saving"

  // Derive the list of missing required field names for the footer hint.
  const missingFields: string[] = []
  if (!data.titel.trim()) missingFields.push("Antragstitel")
  if (!data.projektidee.trim()) missingFields.push("Projektidee")
  if (!data.vertraulichkeit) missingFields.push("Vertraulichkeitsstufe")

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

            {/* Non-dismissible info box */}
            <Alert className="mb-8 flex items-start gap-3 border-border bg-accent/40 text-sm text-foreground">
              <Info className="mt-0.5 size-4 shrink-0 text-primary" />
              <span>
                Diese Angaben braucht die Plattform, um Anforderungen, Belege
                und erste Entwürfe korrekt vorzubereiten.
              </span>
            </Alert>

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

            {/* ── SECTION 1: Projekt ─────────────────────────────────── */}
            <div className="flex flex-col gap-6">
              <SectionHeading
                title="Projekt"
                subtitle="Worum geht es?"
              />

              {/* Antragstitel */}
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="titel">
                  Antragstitel
                  <span className="ml-1 text-destructive" aria-hidden>
                    *
                  </span>
                </Label>
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
                <Label htmlFor="projektidee">
                  Projektidee
                  <span className="ml-1 text-destructive" aria-hidden>
                    *
                  </span>
                </Label>
                <Textarea
                  id="projektidee"
                  value={data.projektidee}
                  onChange={(e) => set("projektidee", e.target.value)}
                  maxLength={PROJEKTIDEE_MAX}
                  rows={5}
                  placeholder="Was ist die Innovation? Für wen? Was ist neu daran?"
                  aria-invalid={!!errors.projektidee}
                  aria-describedby="projektidee-count"
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
            </div>

            <Separator className="my-8" />

            {/* ── SECTION 2: Rahmen ──────────────────────────────────── */}
            <div className="flex flex-col gap-6">
              <SectionHeading
                title="Rahmen"
                subtitle="Förderprofil, Partner und Budget"
              />

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
                <div className="flex h-10 items-center rounded-md border border-border bg-muted/50 px-3 text-sm text-muted-foreground select-none">
                  Innosuisse Beta-Profil — ausgewählte Portalfelder
                </div>
              </div>

              {/* Partner */}
              <div className="flex flex-col gap-3">
                <Label>Projektpartner</Label>
                {data.partner.length > 0 && (
                  <div className="flex flex-col gap-2">
                    {data.partner.map((p) => (
                      <div
                        key={p.id}
                        className="flex items-center gap-2"
                      >
                        <Input
                          value={p.name}
                          onChange={(e) =>
                            updatePartner(p.id, { name: e.target.value })
                          }
                          placeholder="Name der Organisation"
                          aria-label="Partnername"
                          disabled={saving}
                          className="min-w-0 flex-1"
                        />
                        <Select
                          value={p.type}
                          onValueChange={(v) =>
                            updatePartner(p.id, {
                              type: v as IntakePartner["type"],
                            })
                          }
                          disabled={saving}
                        >
                          <SelectTrigger className="w-[200px] shrink-0">
                            <span>{p.type}</span>
                          </SelectTrigger>
                          <SelectContent>
                            <SelectGroup>
                              <SelectItem value="Forschungspartner">
                                Forschungspartner
                              </SelectItem>
                              <SelectItem value="Umsetzungspartner">
                                Umsetzungspartner
                              </SelectItem>
                            </SelectGroup>
                          </SelectContent>
                        </Select>
                        <button
                          type="button"
                          onClick={() => removePartner(p.id)}
                          disabled={saving}
                          aria-label="Partner entfernen"
                          className="flex size-10 shrink-0 items-center justify-center rounded-md text-muted-foreground outline-none transition-colors hover:bg-destructive/10 hover:text-destructive focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50"
                        >
                          <Trash2 className="size-4" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={addPartner}
                  disabled={saving}
                  className="self-start"
                >
                  <Plus data-icon="inline-start" />
                  Partner hinzufügen
                </Button>
              </div>

              {/* Budgetrahmen */}
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="budget">Budgetrahmen (CHF)</Label>
                <Input
                  id="budget"
                  value={data.budgetrahmen}
                  onChange={(e) => set("budgetrahmen", e.target.value)}
                  placeholder="z. B. 350000"
                  aria-invalid={!!errors.budgetrahmen}
                  inputMode="decimal"
                  disabled={saving}
                  className="max-w-[240px]"
                />
                <FieldError message={errors.budgetrahmen} />
              </div>
            </div>

            <Separator className="my-8" />

            {/* ── SECTION 3: Vertraulichkeit ─────────────────────────── */}
            <div className="flex flex-col gap-6">
              <SectionHeading
                title="Vertraulichkeit"
                subtitle="Bestimmt, welche Dienste genutzt werden dürfen"
              />

              <RadioGroup
                value={data.vertraulichkeit}
                onValueChange={(v) =>
                  set("vertraulichkeit", v as DataClass)
                }
                aria-invalid={!!errors.vertraulichkeit}
                className="flex flex-col gap-3"
              >
                {VERTRAULICHKEIT_OPTIONS.map((opt) => {
                  const selected = data.vertraulichkeit === opt.value
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

              <FieldError message={errors.vertraulichkeit} />

              {/* Summary line after selection */}
              {data.vertraulichkeit && (
                <p className="rounded-md bg-accent/40 px-4 py-2.5 text-sm text-foreground">
                  {VERTRAULICHKEIT_SUMMARY[data.vertraulichkeit as DataClass]}
                </p>
              )}
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

            {/* Missing-fields hint — only shown when primary button is disabled */}
            {!submitEnabled && missingFields.length > 0 && (
              <p className="order-last w-full text-xs text-muted-foreground sm:order-none sm:w-auto sm:flex-1 sm:text-right">
                Noch offen:{" "}
                <span className="font-medium text-foreground">
                  {missingFields.join(", ")}
                </span>
              </p>
            )}

            <div className="flex items-center gap-3">
              <Button
                type="button"
                variant="outline"
                disabled={saving}
                onClick={handleDraftSave}
              >
                {saving && (
                  <Loader2
                    data-icon="inline-start"
                    className="animate-spin"
                  />
                )}
                Als Entwurf speichern
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
                Antrag anlegen
              </Button>
            </div>
          </div>
        </div>
      </form>

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
