"use client"

// R3.3 — Import-Review: Upload eines begonnenen Innolink-Antrags (PDF/TXT),
// erkannte Felder prüfen und je Kandidat explizit entscheiden — übernehmen,
// bearbeitet übernehmen oder ignorieren, auch VOR dem ersten Analyse-Lauf
// (ohne Run wird die Übernahme vorgemerkt und beim nächsten Lauf als
// Entwurfsbasis konsumiert). Kein Auto-Accept — auch nicht bei hoher
// Konfidenz; «Unsicher» ist visuell markiert und nie vorausgewählt.
// Flag: innolinkImport (lib/flags.ts).

import * as React from "react"
import { useRouter } from "next/navigation"
import {
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Circle,
  FileUp,
  Info,
  Loader2,
} from "lucide-react"

import { Alert } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Skeleton } from "@/components/ui/skeleton"
import { Textarea } from "@/components/ui/textarea"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  toUploadErrorInfo,
  UploadErrorNotice,
  type UploadErrorInfo,
} from "@/components/quellen/upload-error-notice"
import { useActiveRun } from "@/components/providers/workflow-run-provider"
import { getActiveProjectId } from "@/lib/intake-store"
import {
  createImportCandidates,
  decideImportCandidate,
  decideStructuredImportCandidate,
  getImportCandidates,
  getStructuredImportCandidates,
  ImportError,
  resetImportCandidate,
  resetStructuredImportCandidate,
  reviseImportCandidate,
  reviseStructuredImportCandidate,
  undoImportCandidate,
  undoStructuredImportCandidate,
  type ImportCandidateDto,
  type StructuredImportCandidateDto,
} from "@/lib/imports"
import { getProject } from "@/lib/projects"
import { getSource, uploadFiles, type SourceDocumentDto } from "@/lib/sources"
import type { DataClassification } from "@/lib/data-classification"
import { cn } from "@/lib/utils"

const POLL_MS = 1500
const MAX_POLLS = 80 // ~2 Minuten, danach ehrliche Fehlermeldung

const DECISION_LABELS: Record<string, string> = {
  accepted: "Übernommen",
  saved_as_source: "Nur als Hintergrund verknüpft",
  ignored: "Ignoriert",
  conflict: "Konflikt — Bestätigung nötig",
}

const MAPPING_STATUS_LABELS: Record<string, string> = {
  content_detected: "Inhalt erkannt",
  empty: "Leer",
  legacy_migrated: "Altstruktur migriert",
  uncertain: "Unsicher",
}

/** Anzeige-Label der Entscheidung; «Bearbeitet übernommen» bei edited_text. */
function decisionLabel(candidate: ImportCandidateDto): string {
  if (candidate.decision === "accepted" && candidate.edited_text) {
    return "Bearbeitet übernommen"
  }
  return DECISION_LABELS[candidate.decision] ?? candidate.decision
}

type Phase = "loading" | "no-project" | "upload" | "processing" | "review"

// Sichtbare Verarbeitungsphasen: Prozent nur für den echten Byte-Upload,
// Parsing/Import sind phasenbasiert (kein erfundener Fortschritt).
type ProcessingStep = "uploading" | "extracting" | "checking"

interface ConflictState {
  candidate: ImportCandidateDto
  editedText?: string
}

interface EditState {
  candidate: ImportCandidateDto
  text: string
}

interface StructuredEditState {
  candidate: StructuredImportCandidateDto
  payload: Record<string, unknown>
}

type StructuredConflictState = StructuredEditState

export function ImportReview() {
  const router = useRouter()
  // Zentrale Run-Auswahl (Ladder) — dieselbe Run-ID wie auf allen Screens.
  // statuses/loading speisen die zustandsabhängige Abschluss-Aktion.
  const {
    runId: activeRunId,
    statuses,
    loading: workflowLoading,
  } = useActiveRun()
  const [phase, setPhase] = React.useState<Phase>("loading")
  const [projectId, setProjectId] = React.useState<string | null>(null)
  const [classification, setClassification] =
    React.useState<DataClassification | null>(null)
  const [candidates, setCandidates] = React.useState<ImportCandidateDto[]>([])
  const [structuredCandidates, setStructuredCandidates] = React.useState<
    StructuredImportCandidateDto[]
  >([])
  const [sourceName, setSourceName] = React.useState<string | null>(null)
  const [runId, setRunId] = React.useState<string | null>(null)
  const [busyId, setBusyId] = React.useState<string | null>(null)
  const [expandedId, setExpandedId] = React.useState<string | null>(null)
  const [conflict, setConflict] = React.useState<ConflictState | null>(null)
  const [editing, setEditing] = React.useState<EditState | null>(null)
  const [structuredEditing, setStructuredEditing] =
    React.useState<StructuredEditState | null>(null)
  const [structuredConflict, setStructuredConflict] =
    React.useState<StructuredConflictState | null>(null)
  const [error, setError] = React.useState<UploadErrorInfo | null>(null)
  const [uploadBusy, setUploadBusy] = React.useState(false)
  // Bei Fehler bleibt die gewählte Datei erhalten («Erneut versuchen»).
  const [pendingFile, setPendingFile] = React.useState<File | null>(null)
  const [step, setStep] = React.useState<ProcessingStep>("extracting")
  const [percent, setPercent] = React.useState(0)
  const [hadUpload, setHadUpload] = React.useState(false)

  // -- Initial: aktives Projekt, vorhandene Kandidaten, ggf. eine im Intake
  //    bereits hochgeladene Quelle (?source=…) direkt weiterverarbeiten -----
  React.useEffect(() => {
    let active = true
    const pid = getActiveProjectId()
    if (!pid) {
      setPhase("no-project")
      return
    }
    setProjectId(pid)
    void (async () => {
      try {
        const [project, existing, structured] = await Promise.all([
          getProject(pid),
          getImportCandidates(pid).catch(() => []),
          getStructuredImportCandidates(pid).catch(() => []),
        ])
        if (!active) return
        setClassification(project.data_classification)
        setStructuredCandidates(structured)
        if (existing.length > 0 || structured.length > 0) {
          setCandidates(existing)
          setPhase("review")
          return
        }
        // Vom Intake übergebene, bereits hochgeladene Quelle übernehmen —
        // kein zweiter Upload nötig (die ID steht nur in der URL).
        const adoptId = new URLSearchParams(window.location.search).get(
          "source"
        )
        if (adoptId) {
          setHadUpload(false)
          setStep("extracting")
          setPhase("processing")
          try {
            const doc = await getSource(adoptId)
            if (!active) return
            await processSource(pid, doc)
          } catch {
            if (!active) return
            setPhase("upload")
            setError({
              message:
                "Die hochgeladene Datei konnte nicht übernommen werden. Bitte laden Sie sie hier erneut hoch.",
            })
          }
          return
        }
        setPhase("upload")
      } catch {
        if (!active) return
        setError({ message: "Das Projekt konnte nicht geladen werden." })
        setPhase("upload")
      }
    })()
    return () => {
      active = false
    }
  }, [])

  // Aktiver Run aus der zentralen Auswahl — wenn vorhanden, schreibt
  // «Übernehmen» direkt in dessen Feld-Entwürfe (heutige Semantik).
  React.useEffect(() => {
    if (activeRunId) setRunId(activeRunId)
  }, [activeRunId])

  // -- Verarbeitung abwarten → Felder erkennen (frischer Upload UND vom
  //    Intake übergebene Quelle nutzen denselben Pfad) -----------------------
  async function processSource(pid: string, doc: SourceDocumentDto) {
    setSourceName(doc.name)
    setStep("extracting")
    const processed = await waitForProcessing(doc)
    if (processed.status !== "processed") {
      // Fail-closed aus der Ingestion: Scan/verschlüsselt/kaputt — mit
      // Ursache aus dem Backend (error_code), sofern vorhanden.
      setPhase("upload")
      if (processed.status === "needs_manual_input") {
        setError({
          message:
            processed.error_code === "SOURCE_PDF_ENCRYPTED"
              ? "Das PDF ist passwortgeschützt — es lässt sich kein Text extrahieren. Die Datei bleibt als Quelle gespeichert; bitte entfernen Sie den Passwortschutz oder übertragen Sie die Inhalte manuell."
              : "Aus dieser Datei lässt sich kein Text extrahieren (z. B. Scan ohne Textlayer). Die Datei bleibt als Quelle gespeichert — bitte Inhalte manuell übertragen.",
          code: processed.error_code ?? undefined,
        })
      } else {
        setError({
          message:
            "Die Datei konnte nicht verarbeitet werden. Die Datei bleibt als Quelle gespeichert — bitte Inhalte manuell übertragen.",
          code: processed.error_code ?? undefined,
        })
      }
      return
    }
    setStep("checking")
    const created = await createImportCandidates(pid, doc.source_id)
    setCandidates(created)
    setStructuredCandidates(await getStructuredImportCandidates(pid))
    setPhase("review")
  }

  // -- Upload → Verarbeitung abwarten → Felder erkennen ---------------------
  async function handleFile(file: File) {
    if (!projectId || !classification) return
    setError(null)
    setUploadBusy(true)
    setPendingFile(file)
    setHadUpload(true)
    setStep("uploading")
    setPercent(0)
    setPhase("processing")
    setSourceName(file.name)
    try {
      const [doc] = await uploadFiles(projectId, [file], classification, {
        onProgress: setPercent,
      })
      await processSource(projectId, doc)
      setPendingFile(null)
    } catch (err) {
      setPhase("upload")
      setError(toUploadErrorInfo(err, "Der Upload ist fehlgeschlagen."))
    } finally {
      setUploadBusy(false)
    }
  }

  async function waitForProcessing(
    doc: SourceDocumentDto
  ): Promise<SourceDocumentDto> {
    let current = doc
    for (let i = 0; i < MAX_POLLS; i++) {
      if (
        current.status === "processed" ||
        current.status === "needs_manual_input" ||
        current.status === "failed"
      ) {
        return current
      }
      await new Promise((r) => setTimeout(r, POLL_MS))
      current = await getSource(doc.source_id)
    }
    return current
  }

  // -- Entscheidungen --------------------------------------------------------
  async function decide(
    candidate: ImportCandidateDto,
    decision: "accepted" | "saved_as_source" | "ignored",
    confirmOverwrite = false,
    editedText?: string
  ) {
    const pid = projectId
    if (!pid) return
    setError(null)
    setBusyId(candidate.import_candidate_id)
    try {
      const payload = {
        decision,
        // Mit aktivem Run schreibt «Übernehmen» direkt in den Run-Draft;
        // ohne Run wird die Übernahme vorgemerkt (Konsum beim nächsten Lauf).
        ...(decision === "accepted" && runId ? { run_id: runId } : {}),
        ...(decision === "accepted" && editedText !== undefined
          ? { edited_text: editedText }
          : {}),
        ...(confirmOverwrite ? { confirm_overwrite: true } : {}),
        ...(candidate.current_revision_id
          ? {
              project_id: pid,
              source_id: candidate.source_id,
              expected_revision_id: candidate.current_revision_id,
            }
          : {}),
      }
      const isRevision = candidate.decision !== "pending"
      const updated =
        isRevision && candidate.current_revision_id
          ? await reviseImportCandidate(candidate.import_candidate_id, {
              ...payload,
              project_id: pid,
              source_id: candidate.source_id,
              expected_revision_id: candidate.current_revision_id,
            })
          : await decideImportCandidate(candidate.import_candidate_id, payload)
      setCandidates((prev) =>
        prev.map((c) =>
          c.import_candidate_id === updated.import_candidate_id ? updated : c
        )
      )
    } catch (err) {
      if (err instanceof ImportError && err.code === "import_conflict") {
        // Der Konflikt ist selbst eine neue Revision. Vor der bewussten
        // Bestätigung deshalb den aktuellen Ressourcenstand laden, damit der
        // Dialog nie mit der erwarteten Revision der Erstentscheidung sendet.
        const refreshed = await getImportCandidates(pid)
        setCandidates(refreshed)
        setConflict({
          candidate:
            refreshed.find(
              (item) => item.import_candidate_id === candidate.import_candidate_id
            ) ?? candidate,
          editedText,
        })
      } else {
        setError(
          toUploadErrorInfo(
            err,
            "Die Entscheidung konnte nicht gespeichert werden."
          )
        )
      }
    } finally {
      setBusyId(null)
    }
  }

  async function decideStructured(
    candidate: StructuredImportCandidateDto,
    decision: "accepted" | "ignored",
    editedPayload?: Record<string, unknown>,
    confirmOverwrite = false
  ) {
    const pid = projectId
    if (!pid) return
    setError(null)
    setBusyId(candidate.candidate_id)
    try {
      const payload = {
        decision,
        ...(editedPayload ? { edited_payload_json: editedPayload } : {}),
        ...(confirmOverwrite ? { confirm_overwrite: true } : {}),
        ...(candidate.current_revision_id
          ? {
              project_id: pid,
              source_id: candidate.source_id,
              expected_revision_id: candidate.current_revision_id,
            }
          : {}),
      }
      const isRevision = candidate.decision !== "pending"
      const updated =
        isRevision && candidate.current_revision_id
          ? await reviseStructuredImportCandidate(candidate.candidate_id, {
              ...payload,
              project_id: pid,
              source_id: candidate.source_id,
              expected_revision_id: candidate.current_revision_id,
            })
          : await decideStructuredImportCandidate(candidate.candidate_id, payload)
      setStructuredCandidates((prev) =>
        prev.map((item) =>
          item.candidate_id === updated.candidate_id ? updated : item
        )
      )
    } catch (err) {
      if (
        err instanceof ImportError &&
        ["structured_import_conflict", "structured_import_partner_ambiguous"].includes(
          err.code
        )
      ) {
        const refreshed = await getStructuredImportCandidates(pid)
        setStructuredCandidates(refreshed)
        const current =
          refreshed.find((item) => item.candidate_id === candidate.candidate_id) ??
          candidate
        if (err.code === "structured_import_conflict") {
          setStructuredConflict({
            candidate: current,
            payload: editedPayload ?? candidate.effective_payload_json,
          })
        } else {
          setError(toUploadErrorInfo(err, "Der Partner ist nicht eindeutig zuordenbar."))
        }
      } else {
        setError(
          toUploadErrorInfo(
            err,
            "Die strukturierte Entscheidung konnte nicht gespeichert werden."
          )
        )
      }
    } finally {
      setBusyId(null)
    }
  }

  async function controlNarrative(
    candidate: ImportCandidateDto,
    action: "reset" | "undo"
  ) {
    if (!projectId) return
    setBusyId(candidate.import_candidate_id)
    setError(null)
    try {
      const updated =
        action === "reset"
          ? await resetImportCandidate(candidate, projectId, runId ?? undefined)
          : await undoImportCandidate(candidate, projectId)
      setCandidates((current) =>
        current.map((item) =>
          item.import_candidate_id === updated.import_candidate_id ? updated : item
        )
      )
    } catch (err) {
      const [narrative, structured] = await Promise.all([
        getImportCandidates(projectId),
        getStructuredImportCandidates(projectId),
      ])
      setCandidates(narrative)
      setStructuredCandidates(structured)
      setError(toUploadErrorInfo(err, "Die Importentscheidung konnte nicht geändert werden."))
    } finally {
      setBusyId(null)
    }
  }

  async function controlStructured(
    candidate: StructuredImportCandidateDto,
    action: "reset" | "undo"
  ) {
    if (!projectId) return
    setBusyId(candidate.candidate_id)
    setError(null)
    try {
      const updated =
        action === "reset"
          ? await resetStructuredImportCandidate(candidate, projectId)
          : await undoStructuredImportCandidate(candidate, projectId)
      setStructuredCandidates((current) =>
        current.map((item) =>
          item.candidate_id === updated.candidate_id ? updated : item
        )
      )
    } catch (err) {
      const [narrative, structured] = await Promise.all([
        getImportCandidates(projectId),
        getStructuredImportCandidates(projectId),
      ])
      setCandidates(narrative)
      setStructuredCandidates(structured)
      setError(toUploadErrorInfo(err, "Die Importentscheidung konnte nicht geändert werden."))
    } finally {
      setBusyId(null)
    }
  }

  // -- Abschluss -------------------------------------------------------------
  const open = candidates.filter(
    (c) => c.decision === "pending" || c.decision === "conflict"
  )
  const structuredOpen = structuredCandidates.filter(
    (candidate) =>
      candidate.interaction_mode === "actionable" &&
      (candidate.decision === "pending" || candidate.decision === "conflict")
  )
  const actionableStructured = structuredCandidates.filter(
    (candidate) => candidate.interaction_mode === "actionable"
  )
  const totalCandidates = candidates.length + actionableStructured.length
  const allDecided =
    totalCandidates > 0 && open.length === 0 && structuredOpen.length === 0
  const openCount = open.length + structuredOpen.length

  // Zum nächsten offenen Kandidaten springen (strukturierte zuerst — sie
  // stehen oben auf der Seite), Textkandidaten zusätzlich aufklappen.
  function reviewNextCandidate() {
    if (structuredOpen.length > 0) {
      document
        .getElementById("strukturierte-kandidaten")
        ?.scrollIntoView({ behavior: "smooth", block: "start" })
      return
    }
    const next = open[0]
    if (!next) return
    setExpandedId(next.import_candidate_id)
    document
      .getElementById(next.import_candidate_id)
      ?.scrollIntoView({ behavior: "smooth", block: "start" })
  }

  // Zustandsabhängige Abschluss-Aktion (der EINE nächste Schritt): führt nie
  // ohne abgeschlossenen Analyse-Lauf zu einer leeren Qualitätsprüfung.
  const nextStep: {
    label: string
    onClick?: () => void
    variant: "default" | "outline"
    disabled?: boolean
  } =
    openCount > 0
      ? {
          label: "Nächsten Kandidaten prüfen",
          onClick: reviewNextCandidate,
          variant: "outline",
        }
      : workflowLoading
        ? {
            label: "Nächster Schritt wird ermittelt …",
            variant: "outline",
            disabled: true,
          }
        : !activeRunId && statuses.partner !== "abgeschlossen"
          ? {
              label: "Weiter zu Partner & Budget",
              onClick: () => router.push("/partner"),
              variant: allDecided ? "default" : "outline",
            }
          : !activeRunId
            ? {
                label: "Analyse & Recherche starten",
                onClick: () => router.push("/quellen"),
                variant: allDecided ? "default" : "outline",
              }
            : {
                label: "Zur Fix Queue",
                onClick: () => router.push("/review"),
                variant: allDecided ? "default" : "outline",
              }

  // -- Render ----------------------------------------------------------------
  if (phase === "loading") {
    return (
      <div className="mx-auto w-full max-w-[880px] px-6 py-8">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="mt-4 h-32 w-full" />
      </div>
    )
  }

  if (phase === "no-project") {
    return (
      <div className="mx-auto w-full max-w-[880px] px-6 py-8">
        <h1 className="text-2xl font-semibold text-foreground">Antrag importieren</h1>
        <Alert className="mt-6 flex items-start gap-3 border-border bg-accent/40 text-sm">
          <Info className="mt-0.5 size-4 shrink-0 text-primary" />
          <span>
            Es ist kein Projekt ausgewählt. Bitte legen Sie zuerst unter
            «Projekt anlegen» ein Projekt an und laden Sie dort Ihren
            Innolink-Antrag (PDF) hoch.
          </span>
        </Alert>
        <Button className="mt-4" onClick={() => router.push("/intake")}>
          Projekt anlegen
        </Button>
      </div>
    )
  }

  return (
    <div className="mx-auto w-full max-w-[880px] px-6 py-8">
      <div className="mb-6 flex flex-col gap-1">
        <h1 className="text-balance text-2xl font-semibold text-foreground">
          Antrag importieren
        </h1>
        <p className="text-sm text-muted-foreground">
          Erkannte Feldinhalte prüfen und einzeln übernehmen — nichts wird
          automatisch übernommen.
        </p>
      </div>

      {error && (
        <div className="mb-6">
          <UploadErrorNotice
            error={error}
            onRetry={
              phase === "upload" && pendingFile
                ? () => {
                    const file = pendingFile
                    if (file) void handleFile(file)
                  }
                : undefined
            }
            retryDisabled={uploadBusy}
          />
        </div>
      )}

      {phase === "upload" && (
        <Card className="flex flex-col items-center gap-4 border-dashed p-10 text-center">
          <FileUp className="size-8 text-muted-foreground" />
          <div className="flex flex-col gap-1">
            <p className="text-sm font-medium text-foreground">
              Innolink-Export hochladen (PDF oder Text)
            </p>
            <p className="text-xs text-muted-foreground">
              Der Antrag wird als Quelle gespeichert und deterministisch den
              Portal-Feldern zugeordnet — ohne KI, ohne automatische Übernahme.
            </p>
          </div>
          <label className="inline-flex">
            <input
              type="file"
              accept=".pdf,.txt,application/pdf,text/plain"
              className="sr-only"
              data-testid="import-file-input"
              disabled={uploadBusy}
              onChange={(e) => {
                const file = e.target.files?.[0]
                if (file) void handleFile(file)
                e.currentTarget.value = ""
              }}
            />
            <span
              className={cn(
                "inline-flex h-9 cursor-pointer items-center justify-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground shadow hover:bg-primary/90",
                uploadBusy && "pointer-events-none opacity-50"
              )}
            >
              Datei auswählen
            </span>
          </label>
        </Card>
      )}

      {phase === "processing" && (
        <Card
          className="flex flex-col gap-3 p-6 text-sm"
          aria-live="polite"
          data-testid="import-progress"
        >
          <p className="font-medium text-foreground">
            {sourceName ? `«${sourceName}» wird übernommen` : "Die Datei wird übernommen"}
          </p>
          <div className="flex flex-col gap-1.5">
            {hadUpload && (
              <PhaseLine
                state={step === "uploading" ? "active" : "done"}
                label={
                  step === "uploading"
                    ? `Upload läuft … ${percent} %`
                    : "Hochgeladen"
                }
              />
            )}
            <PhaseLine
              state={step === "uploading" ? "todo" : "done"}
              label="Gespeichert"
            />
            <PhaseLine
              state={
                step === "extracting"
                  ? "active"
                  : step === "checking"
                    ? "done"
                    : "todo"
              }
              label="Text wird extrahiert"
            />
            <PhaseLine
              state={step === "checking" ? "active" : "todo"}
              label="Import wird geprüft"
            />
          </div>
        </Card>
      )}

      {phase === "review" && (
        <div className="flex flex-col gap-4" data-testid="import-review">
          <Alert className="flex items-start gap-3 border-border bg-accent/40 text-sm">
            <Info className="mt-0.5 size-4 shrink-0 text-primary" />
            <span>
              {totalCandidates} Kandidaten erkannt. «Unsicher» markierte Einträge
              brauchen besondere Prüfung und werden nie automatisch übernommen.
            </span>
          </Alert>

          {!runId && (
            <Alert className="flex items-start gap-3 border-border bg-accent/40 text-sm">
              <Info className="mt-0.5 size-4 shrink-0 text-primary" />
              <span>
                Übernommene Inhalte fliessen beim nächsten Analyse-Lauf als
                Entwurfsbasis in die Feld-Entwürfe ein.
              </span>
            </Alert>
          )}

          {structuredCandidates.length > 0 && (
            <section
              id="strukturierte-kandidaten"
              className="grid gap-4"
              data-testid="structured-import-review"
            >
              <div>
                <h2 className="text-base font-semibold">Strukturierte Angaben</h2>
                <p className="text-sm text-muted-foreground">
                  Projekt-, Partner- und Budgetwerte werden erst nach Ihrer
                  ausdrücklichen Bestätigung gespeichert.
                </p>
              </div>
              {(
                [
                  ["project_metadata", "Projektmetadaten"],
                  ["partner", "Partner"],
                  ["budget", "Budget"],
                  ["answer", "Strukturierte Antworten"],
                ] as const
              ).map(([kind, heading]) => {
                const group = structuredCandidates.filter(
                  (candidate) => candidate.candidate_kind === kind
                )
                if (group.length === 0) return null
                return (
                  <div key={kind} className="grid gap-2">
                    <h3 className="text-sm font-medium">{heading}</h3>
                    {group.map((candidate) => (
                      <StructuredCandidateRow
                        key={candidate.candidate_id}
                        candidate={candidate}
                        busy={busyId === candidate.candidate_id}
                        onAccept={() => void decideStructured(candidate, "accepted")}
                        onEdit={() =>
                          setStructuredEditing({
                            candidate,
                            payload: Object.fromEntries(
                              Object.entries(candidate.effective_payload_json).filter(
                                ([key]) => key !== "raw_value"
                              )
                            ),
                          })
                        }
                        onIgnore={() => void decideStructured(candidate, "ignored")}
                        onReset={() => void controlStructured(candidate, "reset")}
                        onUndo={() => void controlStructured(candidate, "undo")}
                      />
                    ))}
                  </div>
                )
              })}
            </section>
          )}

          {candidates.length > 0 && (
            <h2 className="pt-2 text-base font-semibold">Antragstexte</h2>
          )}

          <div className="flex flex-col gap-3">
            {candidates.map((candidate) => (
              <CandidateRow
                key={candidate.import_candidate_id}
                candidate={candidate}
                expanded={expandedId === candidate.import_candidate_id}
                onToggle={() =>
                  setExpandedId((prev) =>
                    prev === candidate.import_candidate_id
                      ? null
                      : candidate.import_candidate_id
                  )
                }
                busy={busyId === candidate.import_candidate_id}
                onDecide={(decision) => void decide(candidate, decision)}
                onEdit={() =>
                  setEditing({
                    candidate,
                    text: candidate.extracted_text,
                  })
                }
                onReset={() => void controlNarrative(candidate, "reset")}
                onUndo={() => void controlNarrative(candidate, "undo")}
              />
            ))}
          </div>

          <div className="mt-2 flex items-center justify-between gap-3">
            <p className="text-sm text-muted-foreground">
              {allDecided
                ? activeRunId
                  ? "Alle Kandidaten sind entschieden."
                  : "Alle Kandidaten sind entschieden. Die Qualitätsprüfung folgt nach dem ersten Analyse-Lauf."
                : `${openCount} von ${totalCandidates} Kandidaten offen.`}
            </p>
            {/* data-testid bleibt in allen Zuständen gleich (Selektor-Kontinuität). */}
            <Button
              onClick={nextStep.onClick}
              variant={nextStep.variant}
              disabled={nextStep.disabled}
              data-testid="import-to-fix-queue"
            >
              {nextStep.label}
            </Button>
          </div>
        </div>
      )}

      {/* Bearbeiten & übernehmen: Original bleibt als Auszug erhalten */}
      <Dialog open={editing !== null} onOpenChange={(o) => !o && setEditing(null)}>
        <DialogContent className="flex max-h-[85dvh] flex-col overflow-hidden sm:max-w-xl">
          <DialogHeader>
            <DialogTitle>Bearbeiten &amp; übernehmen</DialogTitle>
            <DialogDescription>
              Passen Sie den erkannten Text für «{editing?.candidate.label}» an,
              bevor Sie ihn übernehmen. Der Originalauszug bleibt zum Vergleich
              erhalten.
            </DialogDescription>
          </DialogHeader>
          <div className="grid min-h-0 flex-1 content-start gap-1.5 overflow-y-auto">
            {(editing?.candidate.section_metadata ?? [])
              .filter((section) => section.requires_manual_assignment)
              .map((section) => (
                <Alert
                  key={section.target_sections.join("-")}
                  className="mb-2 border-orange-300 text-sm dark:border-orange-800"
                >
                  <div className="grid gap-2">
                    <p>
                      Zielabschnitt {section.target_sections.join(" / ")}: Die
                      Altangabe ist mehrdeutig und muss von Ihnen fachlich
                      eingeordnet werden. Daraus wird keine FTO- oder
                      IP-Schlussfolgerung abgeleitet.
                    </p>
                    {section.candidate_text && (
                      <pre className="max-h-32 overflow-auto whitespace-pre-wrap text-xs">
                        {section.candidate_text}
                      </pre>
                    )}
                  </div>
                </Alert>
              ))}
            <Textarea
              aria-label="Text für die Übernahme bearbeiten"
              value={editing?.text ?? ""}
              onChange={(event) =>
                setEditing((prev) =>
                  prev ? { ...prev, text: event.target.value } : prev
                )
              }
              rows={12}
            />
            <p className="text-xs text-muted-foreground">
              {editing?.text.length ?? 0} Zeichen
            </p>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditing(null)}>
              Abbrechen
            </Button>
            <Button
              data-testid="import-accept-edited"
              disabled={!editing || !editing.text.trim()}
              title={
                editing && !editing.text.trim()
                  ? "Der Text darf nicht leer sein."
                  : undefined
              }
              onClick={() => {
                const current = editing
                setEditing(null)
                if (current) {
                  void decide(current.candidate, "accepted", false, current.text)
                }
              }}
            >
              Bearbeitet übernehmen
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Konflikt: bestehender bearbeiteter Entwurf — explizite Bestätigung */}
      <Dialog open={conflict !== null} onOpenChange={(o) => !o && setConflict(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Bestehenden Entwurf ersetzen?</DialogTitle>
            <DialogDescription>
              Für «{conflict?.candidate.label}» existiert bereits ein bearbeiteter
              Entwurf. Übernehmen ersetzt den aktuellen Text durch den
              importierten Inhalt. Der bisherige Stand bleibt in der
              Versionshistorie erhalten.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConflict(null)}>
              Abbrechen
            </Button>
            <Button
              data-testid="import-confirm-overwrite"
              onClick={() => {
                const current = conflict
                setConflict(null)
                if (current) {
                  void decide(
                    current.candidate,
                    "accepted",
                    true,
                    current.editedText
                  )
                }
              }}
            >
              Entwurf ersetzen
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={structuredEditing !== null}
        onOpenChange={(open) => !open && setStructuredEditing(null)}
      >
        <DialogContent className="flex max-h-[85dvh] flex-col overflow-hidden sm:max-w-xl">
          <DialogHeader>
            <DialogTitle>Strukturierte Angabe bearbeiten &amp; übernehmen</DialogTitle>
            <DialogDescription>
              Prüfen Sie «{structuredEditing?.candidate.label}». Der erkannte
              Originalwert bleibt am Importkandidaten erhalten.
            </DialogDescription>
          </DialogHeader>
          <div className="min-h-0 flex-1 overflow-y-auto pr-1">
            {structuredEditing && (
              <StructuredPayloadEditor
                candidate={structuredEditing.candidate}
                payload={structuredEditing.payload}
                onChange={(payload) =>
                  setStructuredEditing((current) =>
                    current ? { ...current, payload } : current
                  )
                }
              />
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setStructuredEditing(null)}>
              Abbrechen
            </Button>
            <Button
              data-testid="structured-import-accept-edited"
              onClick={() => {
                const current = structuredEditing
                setStructuredEditing(null)
                if (current) {
                  void decideStructured(
                    current.candidate,
                    "accepted",
                    current.payload
                  )
                }
              }}
            >
              Bearbeitet übernehmen
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={structuredConflict !== null}
        onOpenChange={(open) => !open && setStructuredConflict(null)}
      >
        <DialogContent className="sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>Bestehenden Wert ersetzen?</DialogTitle>
            <DialogDescription>
              Vergleichen Sie den aktuellen Projektstand mit dem erkannten
              PDF-Wert. Ohne diese Bestätigung wird nichts überschrieben.
            </DialogDescription>
          </DialogHeader>
          {structuredConflict && (
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="rounded-md border p-3">
                <h3 className="mb-2 text-sm font-medium">Aktueller Wert</h3>
                <PayloadDisplay
                  payload={structuredConflict.candidate.current_value_json ?? {}}
                />
              </div>
              <div className="rounded-md border p-3">
                <h3 className="mb-2 text-sm font-medium">Aus PDF erkannt</h3>
                <PayloadDisplay payload={structuredConflict.payload} />
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setStructuredConflict(null)}>
              Abbrechen
            </Button>
            <Button
              data-testid="structured-import-confirm-overwrite"
              onClick={() => {
                const current = structuredConflict
                setStructuredConflict(null)
                if (current) {
                  void decideStructured(
                    current.candidate,
                    "accepted",
                    current.payload,
                    true
                  )
                }
              }}
            >
              Geprüft überschreiben
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

const STRUCTURED_FIELD_LABELS: Record<string, string> = {
  title: "Projekttitel",
  title_en: "Projekttitel (Englisch)",
  start_date: "Projektstart",
  end_date: "Projektende",
  duration_months: "Projektdauer in Monaten",
  direct_total_project_costs_excluding_overhead: "Direkte Projektkosten ohne Overhead",
  implementation_own_contribution: "Eigenleistung Umsetzungspartner",
  cash_contribution: "Barbeitrag",
  total_requested_funding: "Beantragte Förderung ohne Overhead",
  total_requested_funding_including_overhead:
    "Beantragte Förderung inkl. Overhead (nur Information)",
  name: "Name",
  partner_type: "Partnertyp",
  project_role: "Rolle im Projekt",
  country: "Land",
  department: "Department",
  industry: "Branche",
  fte: "FTE",
  swiss_value_creation: "Schweizer Wertschöpfung",
  personnel_independence_status: "Personelle Unabhängigkeit",
  financial_independence_status: "Finanzielle Unabhängigkeit",
  review_comment: "Kommentar zur Prüfung",
  sanction_answer: "Schwere Sanktion angegeben",
  comment: "Kommentar",
  management_hours: "Management-Stunden",
  total_project_hours: "Gesamtstunden",
}

const STRUCTURED_HIDDEN_KEYS = new Set([
  "raw_value",
  "personnel_answers",
  "financial_confirmations",
])

function formatStructuredValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "Nicht erkannt"
  if (typeof value === "boolean") return value ? "Ja" : "Nein"
  if (typeof value === "object") return JSON.stringify(value)
  return String(value)
}

function PayloadDisplay({ payload }: { payload: Record<string, unknown> }) {
  const representative = payload.official_representative as
    | { display_name?: string }
    | null
    | undefined
  return (
    <dl className="grid grid-cols-[minmax(9rem,auto)_1fr] gap-x-3 gap-y-1 text-xs">
      {Object.entries(payload)
        .filter(
          ([key]) =>
            !STRUCTURED_HIDDEN_KEYS.has(key) && key !== "official_representative"
        )
        .map(([key, value]) => (
          <React.Fragment key={key}>
            <dt className="text-muted-foreground">
              {STRUCTURED_FIELD_LABELS[key] ?? key}
            </dt>
            <dd className="break-words text-foreground">
              {formatStructuredValue(value)}
            </dd>
          </React.Fragment>
        ))}
      {representative?.display_name && (
        <div className="col-span-2 mt-1">
          <details>
            <summary className="cursor-pointer text-muted-foreground">
              Personenangabe zur offiziellen Vertretung prüfen
            </summary>
            <p className="mt-1 text-foreground">{representative.display_name}</p>
            <p className="text-muted-foreground">
              Es werden keine E-Mail-Adresse oder Telefonnummer übernommen.
            </p>
          </details>
        </div>
      )}
    </dl>
  )
}

function StructuredCandidateRow({
  candidate,
  busy,
  onAccept,
  onEdit,
  onIgnore,
  onReset,
  onUndo,
}: Readonly<{
  candidate: StructuredImportCandidateDto
  busy: boolean
  onAccept: () => void
  onEdit: () => void
  onIgnore: () => void
  onReset: () => void
  onUndo: () => void
}>) {
  const comparisonOnly = candidate.interaction_mode === "comparison_only"
  const open =
    !comparisonOnly &&
    (candidate.decision === "pending" || candidate.decision === "conflict")
  const uncertain = candidate.confidence === "uncertain"
  const allowedActions = candidate.allowed_actions ??
    (candidate.decision === "accepted"
      ? ["edit", "reset", "undo"]
      : candidate.decision === "ignored"
        ? ["reset", "undo"]
        : [])
  return (
    <Card
      className={cn(
        "grid gap-3 p-4",
        uncertain && open && "border-orange-300 dark:border-orange-800"
      )}
      data-testid="structured-import-candidate"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="grid gap-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-medium">{candidate.label}</span>
            <Badge
              variant="outline"
              className={cn(
                uncertain && "border-orange-400 text-orange-700 dark:text-orange-300"
              )}
            >
              {uncertain ? "Unsicher" : "Inhalt erkannt"}
            </Badge>
            {comparisonOnly && <Badge variant="outline">Nur Vergleich</Badge>}
            {candidate.source_location && (
              <span className="text-xs text-muted-foreground">
                Fundseite: {candidate.source_location}
              </span>
            )}
          </div>
          {candidate.decision !== "pending" && (
            <span className="text-xs text-muted-foreground">
              {candidate.decision === "accepted"
                ? candidate.edited_payload_json
                  ? "Bearbeitet übernommen"
                  : "Übernommen – menschlich bestätigt"
                : candidate.decision === "ignored"
                  ? "Ignoriert"
                  : "Konflikt – Bestätigung nötig"}
            </span>
          )}
        </div>
        {open && (
          <div className="flex flex-wrap gap-2">
            <Button size="sm" disabled={busy || candidate.requires_manual_edit} onClick={onAccept}>
              Übernehmen
            </Button>
            <Button size="sm" variant="outline" disabled={busy} onClick={onEdit}>
              Bearbeiten &amp; übernehmen
            </Button>
            <Button size="sm" variant="ghost" disabled={busy} onClick={onIgnore}>
              Ignorieren
            </Button>
          </div>
        )}
        {!open && !comparisonOnly && (
          <div className="flex flex-wrap gap-2">
            {allowedActions.includes("edit") && (
              <Button size="sm" variant="outline" disabled={busy} onClick={onEdit}>
                Bearbeiten
              </Button>
            )}
            {allowedActions.includes("reset") && (
              <Button size="sm" variant="outline" disabled={busy} onClick={onReset}>
                PDF-Wert wiederherstellen
              </Button>
            )}
            {allowedActions.includes("undo") && (
              <Button size="sm" variant="ghost" disabled={busy} onClick={onUndo}>
                Übernahme zurücknehmen
              </Button>
            )}
          </div>
        )}
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="rounded-md border bg-accent/10 p-3">
          <p className="mb-2 text-xs font-medium">Aus PDF erkannt</p>
          <PayloadDisplay payload={candidate.effective_payload_json} />
        </div>
        {candidate.current_value_json && (
          <div className="rounded-md border bg-accent/10 p-3">
            <p className="mb-2 text-xs font-medium">Aktueller Wert</p>
            <PayloadDisplay payload={candidate.current_value_json} />
          </div>
        )}
      </div>
      {comparisonOnly && (
        <p className="text-xs text-muted-foreground">
          {candidate.duration_comparison_status === "duration_match"
            ? "PDF-Wert und abgeleitete Dauer stimmen überein."
            : candidate.duration_comparison_status === "duration_conflict"
              ? "Der PDF-Wert weicht von der abgeleiteten Projektdauer ab."
              : candidate.duration_comparison_status === "duration_boundary_conflict"
                ? "Die Datumsgrenzen decken keine vollständigen Kalendermonate ab."
                : "Ohne vollständiges Start- und Enddatum ist kein Vergleich möglich."}
          {candidate.derived_duration_months !== null &&
            ` Abgeleitet: ${candidate.derived_duration_months} Monate.`}
        </p>
      )}
      {candidate.has_conflict && open && (
        <p className="text-xs text-orange-700 dark:text-orange-300">
          Der aktuelle Wert weicht vom PDF ab. Eine Übernahme verlangt eine
          ausdrückliche Bestätigung.
        </p>
      )}
      <details className="text-xs text-muted-foreground">
        <summary className="cursor-pointer">Technische Details</summary>
        <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-2 gap-y-1">
          <dt>Zielschlüssel</dt>
          <dd className="break-all">{candidate.target_key}</dd>
          <dt>Mapping-Version</dt>
          <dd>{candidate.mapping_version}</dd>
          <dt>Kandidaten-ID</dt>
          <dd className="break-all">{candidate.candidate_id}</dd>
          {candidate.conflict_reason && <dt>Konfliktcode</dt>}
          {candidate.conflict_reason && <dd>{candidate.conflict_reason}</dd>}
        </dl>
      </details>
    </Card>
  )
}

function StructuredPayloadEditor({
  candidate,
  payload,
  onChange,
}: Readonly<{
  candidate: StructuredImportCandidateDto
  payload: Record<string, unknown>
  onChange: (payload: Record<string, unknown>) => void
}>) {
  const update = (key: string, value: unknown) => onChange({ ...payload, [key]: value })
  const visible = Object.entries(payload).filter(
    ([key]) => !STRUCTURED_HIDDEN_KEYS.has(key) && key !== "official_representative"
  )
  const representative = payload.official_representative as
    | { display_name?: string }
    | null
    | undefined
  return (
    <div className="grid gap-4">
      {candidate.confidence === "uncertain" && (
        <Alert className="border-orange-300 text-sm dark:border-orange-800">
          Unsichere Werte müssen vor der Übernahme fachlich geprüft werden.
        </Alert>
      )}
      {visible.map(([key, value]) => {
        const label = STRUCTURED_FIELD_LABELS[key] ?? key
        if (typeof value === "boolean" || key === "sanction_answer") {
          return (
            <div key={key} className="grid gap-1.5">
              <Label htmlFor={`structured-${key}`}>{label}</Label>
              <select
                id={`structured-${key}`}
                className="h-9 rounded-md border border-input bg-background px-3 text-sm"
                value={value === true ? "true" : value === false ? "false" : ""}
                onChange={(event) =>
                  update(
                    key,
                    event.target.value === "" ? null : event.target.value === "true"
                  )
                }
              >
                <option value="">Bitte wählen</option>
                <option value="true">Ja</option>
                <option value="false">Nein</option>
              </select>
            </div>
          )
        }
        if (key === "partner_type") {
          return (
            <div key={key} className="grid gap-1.5">
              <Label htmlFor={`structured-${key}`}>{label}</Label>
              <select
                id={`structured-${key}`}
                className="h-9 rounded-md border border-input bg-background px-3 text-sm"
                value={String(value ?? "")}
                onChange={(event) => update(key, event.target.value)}
              >
                <option value="research_partner">Forschungspartner</option>
                <option value="implementation_partner">Umsetzungspartner</option>
                <option value="other">Weitere</option>
              </select>
            </div>
          )
        }
        if (key.endsWith("independence_status")) {
          return (
            <div key={key} className="grid gap-1.5">
              <Label htmlFor={`structured-${key}`}>{label}</Label>
              <select
                id={`structured-${key}`}
                className="h-9 rounded-md border border-input bg-background px-3 text-sm"
                value={String(value ?? "")}
                onChange={(event) => update(key, event.target.value || null)}
              >
                <option value="">Bitte prüfen</option>
                <option value="confirmed">Im PDF bestätigt</option>
                <option value="needs_input">Weitere Prüfung nötig</option>
                <option value="exception">Ausnahme</option>
              </select>
            </div>
          )
        }
        const numeric = typeof value === "number" || [
          "duration_months",
          "direct_total_project_costs_excluding_overhead",
          "implementation_own_contribution",
          "cash_contribution",
          "total_requested_funding",
          "total_requested_funding_including_overhead",
          "fte",
          "management_hours",
          "total_project_hours",
        ].includes(key)
        return (
          <div key={key} className="grid gap-1.5">
            <Label htmlFor={`structured-${key}`}>{label}</Label>
            <Input
              id={`structured-${key}`}
              type={numeric ? "number" : key.endsWith("_date") ? "date" : "text"}
              value={value === null || value === undefined ? "" : String(value)}
              onChange={(event) =>
                update(
                  key,
                  numeric
                    ? event.target.value === ""
                      ? null
                      : Number(event.target.value)
                    : event.target.value || null
                )
              }
            />
          </div>
        )
      })}
      {candidate.candidate_kind === "partner" && (
        <div className="grid gap-1.5 rounded-md border p-3">
          <Label htmlFor="structured-representative">
            Offizielle Vertretung – nur Name
          </Label>
          <Input
            id="structured-representative"
            value={representative?.display_name ?? ""}
            onChange={(event) =>
              update(
                "official_representative",
                event.target.value
                  ? { display_name: event.target.value }
                  : null
              )
            }
          />
          <p className="text-xs text-muted-foreground">
            Kontaktangaben wie E-Mail oder Telefon werden nicht importiert.
          </p>
        </div>
      )}
    </div>
  )
}

/** Eine sichtbare Verarbeitungsphase (erledigt / aktiv / ausstehend). */
function PhaseLine({
  state,
  label,
}: Readonly<{
  state: "done" | "active" | "todo"
  label: string
}>) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-2 text-sm",
        state === "todo" ? "text-muted-foreground" : "text-foreground"
      )}
    >
      {state === "done" && <CheckCircle2 className="size-4 text-green-600" />}
      {state === "active" && (
        <Loader2 className="size-4 animate-spin text-primary" />
      )}
      {state === "todo" && <Circle className="size-4 text-muted-foreground/50" />}
      {label}
    </span>
  )
}

function CandidateRow({
  candidate,
  expanded,
  onToggle,
  busy,
  onDecide,
  onEdit,
  onReset,
  onUndo,
}: Readonly<{
  candidate: ImportCandidateDto
  expanded: boolean
  onToggle: () => void
  busy: boolean
  onDecide: (decision: "accepted" | "saved_as_source" | "ignored") => void
  onEdit: () => void
  onReset: () => void
  onUndo: () => void
}>) {
  const uncertain = candidate.confidence === "uncertain"
  const allowedActions = candidate.allowed_actions ??
    (candidate.decision === "accepted"
      ? ["edit", "reset", "undo"]
      : candidate.decision === "ignored" || candidate.decision === "saved_as_source"
        ? ["reset", "undo"]
        : [])
  const openForDecision =
    candidate.decision === "pending" || candidate.decision === "conflict"
  const empty = !candidate.extracted_text.trim()
  const sections = candidate.section_metadata ?? []
  const requiresManualAssignment = sections.some(
    (section) => section.requires_manual_assignment
  )
  const status =
    candidate.mapping_status ??
    (empty ? "empty" : uncertain ? "uncertain" : "content_detected")
  const targetSections = Array.from(
    new Set(sections.flatMap((section) => section.target_sections))
  )

  return (
    <Card
      id={candidate.import_candidate_id}
      className={cn(
        "flex flex-col gap-0 p-0",
        uncertain && openForDecision && "border-orange-300 dark:border-orange-800"
      )}
      data-testid="import-candidate"
    >
      <div className="flex items-start justify-between gap-3 p-4">
        <div className="flex min-w-0 flex-col gap-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-medium text-foreground">
              {candidate.label}
            </span>
            <Badge
              variant="outline"
              className={cn(
                status === "uncertain" || uncertain
                  ? "border-orange-400 text-orange-700 dark:text-orange-300"
                  : "text-muted-foreground"
              )}
            >
              {MAPPING_STATUS_LABELS[status] ?? status}
            </Badge>
            {candidate.source_location && (
              <span className="text-xs text-muted-foreground">
                Fundseite: {candidate.source_location}
              </span>
            )}
          </div>
          {targetSections.length > 0 && (
            <p className="text-xs text-muted-foreground">
              Zielabschnitt: {targetSections.join(", ")}
            </p>
          )}
          {candidate.decision !== "pending" && (
            <span
              className={cn(
                "inline-flex items-center gap-1 text-xs",
                candidate.decision === "conflict"
                  ? "text-orange-700 dark:text-orange-300"
                  : "text-muted-foreground"
              )}
            >
              {candidate.decision === "accepted" && (
                <CheckCircle2 className="size-3.5 text-green-600" />
              )}
              {decisionLabel(candidate)}
            </span>
          )}
        </div>

        {openForDecision && (
          <div className="flex max-w-xl shrink-0 flex-col items-end gap-1.5">
            <div className="flex flex-wrap items-center justify-end gap-2">
              <Button
                size="sm"
                disabled={busy || empty || requiresManualAssignment}
                title={
                  empty
                    ? "Dieser Kandidat enthält keinen Text."
                    : requiresManualAssignment
                      ? "Die mehrdeutige Altangabe muss zuerst bearbeitet und fachlich zugeordnet werden."
                      : undefined
                }
                onClick={() => onDecide("accepted")}
              >
                Übernehmen
              </Button>
              <Button
                size="sm"
                variant="outline"
                disabled={busy || (empty && !requiresManualAssignment)}
                title={
                  empty && !requiresManualAssignment
                    ? "Dieser Kandidat enthält keinen Text."
                    : undefined
                }
                onClick={onEdit}
              >
                Bearbeiten &amp; übernehmen
              </Button>
              <Button
                size="sm"
                variant="outline"
                disabled={busy}
                onClick={() => onDecide("saved_as_source")}
              >
                Nur als Hintergrund verknüpfen
              </Button>
              <Button
                size="sm"
                variant="ghost"
                disabled={busy}
                onClick={() => onDecide("ignored")}
              >
                Ignorieren
              </Button>
            </div>
            <p className="max-w-md text-right text-[11px] text-muted-foreground">
              Das PDF ist bereits als Quelle gespeichert. Diese Aktion markiert
              nur den Ausschnitt als relevanten Hintergrund und übernimmt keinen
              Text.
            </p>
          </div>
        )}
        {!openForDecision && (
          <div className="flex max-w-xl shrink-0 flex-wrap justify-end gap-2">
            {allowedActions.includes("edit") && (
              <Button size="sm" variant="outline" disabled={busy} onClick={onEdit}>
                Bearbeiten
              </Button>
            )}
            {allowedActions.includes("reset") && (
              <Button size="sm" variant="outline" disabled={busy} onClick={onReset}>
                PDF-Wert wiederherstellen
              </Button>
            )}
            {allowedActions.includes("undo") && (
              <Button size="sm" variant="ghost" disabled={busy} onClick={onUndo}>
                Übernahme zurücknehmen
              </Button>
            )}
          </div>
        )}
      </div>

      <button
        type="button"
        onClick={onToggle}
        aria-expanded={expanded}
        className="flex items-center gap-1 border-t border-border px-4 py-2 text-left text-xs text-muted-foreground hover:text-foreground"
      >
        {expanded ? (
          <ChevronDown className="size-3.5" />
        ) : (
          <ChevronRight className="size-3.5" />
        )}
        Abschnittsdetails {empty ? "(leer)" : ""}
      </button>
      {expanded && (
        <div className="grid gap-3 border-t border-border bg-accent/20 px-4 py-3">
          {sections.length > 0 ? (
            sections.map((section, index) => (
              <div
                key={`${section.target_sections.join("-")}-${index}`}
                className="grid gap-2 rounded-md border border-border bg-background/70 p-3"
                data-testid="import-section-metadata"
              >
                <div className="flex flex-wrap items-center gap-2 text-xs">
                  <span className="font-medium text-foreground">
                    Zielabschnitt: {section.target_sections.join(" / ")}
                  </span>
                  <Badge
                    variant="outline"
                    className={cn(
                      section.status === "uncertain" &&
                        "border-orange-400 text-orange-700 dark:text-orange-300"
                    )}
                  >
                    {MAPPING_STATUS_LABELS[section.status] ?? section.status}
                  </Badge>
                  {section.source_location && (
                    <span className="text-muted-foreground">
                      Fundseite: {section.source_location}
                    </span>
                  )}
                </div>
                {section.review_note && (
                  <p className="text-xs text-orange-700 dark:text-orange-300">
                    {section.review_note}
                  </p>
                )}
                {section.candidate_text ? (
                  <div className="grid gap-1">
                    <span className="text-xs font-medium">Erkannter Inhalt</span>
                    <pre className="max-h-48 overflow-auto whitespace-pre-wrap text-xs text-foreground">
                      {section.candidate_text}
                    </pre>
                  </div>
                ) : (
                  <p className="text-xs text-muted-foreground">
                    Für diesen Abschnitt wurde kein übernehmbarer Inhalt gefunden.
                  </p>
                )}
                <details className="text-xs text-muted-foreground">
                  <summary className="cursor-pointer">Originalausschnitt</summary>
                  {section.original_excerpt ? (
                    <pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap text-foreground">
                      {section.original_excerpt}
                    </pre>
                  ) : (
                    <p className="mt-2">Kein Originalausschnitt vorhanden.</p>
                  )}
                </details>
              </div>
            ))
          ) : empty ? (
            <p className="text-xs text-muted-foreground">
              Für dieses Feld wurde kein Inhalt gefunden — es bleibt zur
              manuellen Bearbeitung offen.
            </p>
          ) : (
            <pre className="max-h-64 overflow-auto whitespace-pre-wrap text-xs text-foreground">
              {candidate.extracted_text}
            </pre>
          )}
          <details className="text-xs text-muted-foreground">
            <summary className="cursor-pointer">Technische Details</summary>
            <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-2 gap-y-1">
              <dt>Feld-ID</dt>
              <dd className="break-all">{candidate.field_id}</dd>
              <dt>Mapping-Version</dt>
              <dd>{candidate.mapping_version}</dd>
            </dl>
          </details>
        </div>
      )}
    </Card>
  )
}
