"use client"

// R3.3 — Import-Review: Upload eines begonnenen Innolink-Antrags (PDF/TXT),
// erkannte Felder prüfen und je Kandidat explizit entscheiden. Kein
// Auto-Accept — auch nicht bei hoher Konfidenz; «Unsicher» ist visuell
// markiert und nie vorausgewählt. Flag: innolinkImport (lib/flags.ts).

import * as React from "react"
import { useRouter } from "next/navigation"
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
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
import { getActiveProjectId } from "@/lib/intake-store"
import {
  createImportCandidates,
  decideImportCandidate,
  getImportCandidates,
  ImportError,
  type ImportCandidateDto,
} from "@/lib/imports"
import { getProject } from "@/lib/projects"
import { createRun, getRun, listProjectRuns, type RunSettings } from "@/lib/runs"
import { getSource, uploadFiles, type SourceDocumentDto } from "@/lib/sources"
import type { DataClassification } from "@/lib/data-classification"
import { cn } from "@/lib/utils"

const POLL_MS = 1500
const MAX_POLLS = 80 // ~2 Minuten, danach ehrliche Fehlermeldung

// Deterministische Analyse (keine LLM-/Web-Kosten) — genügt, um die
// Feld-Entwürfe anzulegen, in die übernommen wird.
const RUN_SETTINGS: RunSettings = {
  processing_mode: "deterministic_only",
  max_cost_chf: 0,
  max_llm_calls: 0,
  max_web_calls: 0,
}

const DECISION_LABELS: Record<string, string> = {
  accepted: "Übernommen",
  saved_as_source: "Als Quelle gespeichert",
  ignored: "Ignoriert",
  conflict: "Konflikt — Bestätigung nötig",
}

type Phase = "loading" | "no-project" | "upload" | "processing" | "review"

interface ConflictState {
  candidate: ImportCandidateDto
}

export function ImportReview() {
  const router = useRouter()
  const [phase, setPhase] = React.useState<Phase>("loading")
  const [projectId, setProjectId] = React.useState<string | null>(null)
  const [classification, setClassification] =
    React.useState<DataClassification | null>(null)
  const [candidates, setCandidates] = React.useState<ImportCandidateDto[]>([])
  const [sourceName, setSourceName] = React.useState<string | null>(null)
  const [runId, setRunId] = React.useState<string | null>(null)
  const [runStarting, setRunStarting] = React.useState(false)
  const [busyId, setBusyId] = React.useState<string | null>(null)
  const [expandedId, setExpandedId] = React.useState<string | null>(null)
  const [conflict, setConflict] = React.useState<ConflictState | null>(null)
  const [error, setError] = React.useState<string | null>(null)
  const [uploadBusy, setUploadBusy] = React.useState(false)

  // -- Initial: aktives Projekt, vorhandene Kandidaten, vorhandener Run -----
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
        const [project, existing, runs] = await Promise.all([
          getProject(pid),
          getImportCandidates(pid).catch(() => []),
          listProjectRuns(pid).catch(() => []),
        ])
        if (!active) return
        setClassification(project.data_classification)
        const completed = runs.find((r) => r.status === "completed")
        if (completed) setRunId(completed.run_id)
        if (existing.length > 0) {
          setCandidates(existing)
          setPhase("review")
        } else {
          setPhase("upload")
        }
      } catch {
        if (!active) return
        setError("Das Projekt konnte nicht geladen werden.")
        setPhase("upload")
      }
    })()
    return () => {
      active = false
    }
  }, [])

  // -- Upload → Verarbeitung abwarten → Felder erkennen ---------------------
  async function handleFile(file: File) {
    if (!projectId || !classification) return
    setError(null)
    setUploadBusy(true)
    setPhase("processing")
    setSourceName(file.name)
    try {
      const [doc] = await uploadFiles(projectId, [file], classification)
      const processed = await waitForProcessing(doc)
      if (processed.status !== "processed") {
        // Fail-closed aus der Ingestion: Scan/verschlüsselt/kaputt.
        setPhase("upload")
        setError(
          processed.status === "needs_manual_input"
            ? "Aus dieser Datei lässt sich kein Text extrahieren (z. B. Scan oder verschlüsseltes PDF). Die Datei bleibt als Quelle gespeichert — bitte Inhalte manuell übertragen."
            : "Die Datei konnte nicht verarbeitet werden. Die Datei bleibt als Quelle gespeichert — bitte Inhalte manuell übertragen."
        )
        return
      }
      const created = await createImportCandidates(projectId, doc.source_id)
      setCandidates(created)
      setPhase("review")
    } catch (err) {
      setPhase("upload")
      setError(
        err instanceof Error && err.message
          ? err.message
          : "Der Upload ist fehlgeschlagen."
      )
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

  // -- Analyse starten (nötig für «Übernehmen»: Entwürfe sind run-gebunden) --
  async function handleStartRun() {
    if (!projectId) return
    setError(null)
    setRunStarting(true)
    try {
      const accepted = await createRun(projectId, RUN_SETTINGS)
      for (let i = 0; i < MAX_POLLS; i++) {
        const run = await getRun(accepted.resource_id)
        if (run.status === "completed") {
          setRunId(run.run_id)
          return
        }
        if (["failed", "cancelled", "stopped"].includes(run.status)) {
          setError("Die Analyse konnte nicht abgeschlossen werden.")
          return
        }
        await new Promise((r) => setTimeout(r, POLL_MS))
      }
      setError("Die Analyse dauert länger als erwartet. Bitte später erneut versuchen.")
    } catch (err) {
      setError(
        err instanceof Error && err.message
          ? err.message
          : "Die Analyse konnte nicht gestartet werden."
      )
    } finally {
      setRunStarting(false)
    }
  }

  // -- Entscheidungen --------------------------------------------------------
  async function decide(
    candidate: ImportCandidateDto,
    decision: "accepted" | "saved_as_source" | "ignored",
    confirmOverwrite = false
  ) {
    setError(null)
    setBusyId(candidate.import_candidate_id)
    try {
      const updated = await decideImportCandidate(candidate.import_candidate_id, {
        decision,
        ...(decision === "accepted" && runId ? { run_id: runId } : {}),
        ...(confirmOverwrite ? { confirm_overwrite: true } : {}),
      })
      setCandidates((prev) =>
        prev.map((c) =>
          c.import_candidate_id === updated.import_candidate_id ? updated : c
        )
      )
    } catch (err) {
      if (err instanceof ImportError && err.code === "import_conflict") {
        // Kandidat ist jetzt serverseitig als Konflikt markiert.
        setCandidates((prev) =>
          prev.map((c) =>
            c.import_candidate_id === candidate.import_candidate_id
              ? { ...c, decision: "conflict" }
              : c
          )
        )
        setConflict({ candidate })
      } else {
        setError(
          err instanceof Error && err.message
            ? err.message
            : "Die Entscheidung konnte nicht gespeichert werden."
        )
      }
    } finally {
      setBusyId(null)
    }
  }

  // -- Abschluss -------------------------------------------------------------
  const open = candidates.filter(
    (c) => c.decision === "pending" || c.decision === "conflict"
  )
  const allDecided = candidates.length > 0 && open.length === 0

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
            Es ist kein Antrag ausgewählt. Bitte legen Sie zuerst im Intake einen
            Antrag an und wählen Sie dort «Bestehenden Innolink-Antrag hochladen».
          </span>
        </Alert>
        <Button className="mt-4" onClick={() => router.push("/intake")}>
          Zum Intake
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
        <Alert
          role="alert"
          className="mb-6 flex items-start gap-3 border-destructive/30 bg-destructive/5 text-sm"
        >
          <AlertTriangle className="mt-0.5 size-4 shrink-0 text-destructive" />
          <span>{error}</span>
        </Alert>
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
        <Card className="flex items-center gap-3 p-6 text-sm text-foreground">
          <Loader2 className="size-4 animate-spin text-primary" />
          <span>
            {sourceName
              ? `«${sourceName}» wird verarbeitet und den Feldern zugeordnet …`
              : "Die Datei wird verarbeitet …"}
          </span>
        </Card>
      )}

      {phase === "review" && (
        <div className="flex flex-col gap-4" data-testid="import-review">
          <Alert className="flex items-start gap-3 border-border bg-accent/40 text-sm">
            <Info className="mt-0.5 size-4 shrink-0 text-primary" />
            <span>
              {candidates.length} Felder erkannt. «Unsicher» markierte Einträge
              brauchen besondere Prüfung und werden nie automatisch übernommen.
            </span>
          </Alert>

          {!runId && (
            <Alert className="flex items-start justify-between gap-3 border-border bg-accent/40 text-sm">
              <span className="flex items-start gap-3">
                <Info className="mt-0.5 size-4 shrink-0 text-primary" />
                <span>
                  Zum Übernehmen in die Feld-Entwürfe wird einmal eine Analyse
                  benötigt.
                </span>
              </span>
              <Button
                size="sm"
                onClick={() => void handleStartRun()}
                disabled={runStarting}
                data-testid="import-start-run"
              >
                {runStarting ? "Analyse läuft …" : "Analyse starten"}
              </Button>
            </Alert>
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
                canAccept={Boolean(runId)}
                onDecide={(decision) => void decide(candidate, decision)}
              />
            ))}
          </div>

          <div className="mt-2 flex items-center justify-between gap-3">
            <p className="text-sm text-muted-foreground">
              {allDecided
                ? "Alle Kandidaten sind entschieden."
                : `${open.length} von ${candidates.length} Kandidaten offen.`}
            </p>
            <Button
              onClick={() => router.push("/review")}
              variant={allDecided ? "default" : "outline"}
              data-testid="import-to-fix-queue"
            >
              Zur Fix Queue — Nächste Aufgaben
            </Button>
          </div>
        </div>
      )}

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
                const candidate = conflict?.candidate
                setConflict(null)
                if (candidate) void decide(candidate, "accepted", true)
              }}
            >
              Entwurf ersetzen
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

function CandidateRow({
  candidate,
  expanded,
  onToggle,
  busy,
  canAccept,
  onDecide,
}: Readonly<{
  candidate: ImportCandidateDto
  expanded: boolean
  onToggle: () => void
  busy: boolean
  canAccept: boolean
  onDecide: (decision: "accepted" | "saved_as_source" | "ignored") => void
}>) {
  const uncertain = candidate.confidence === "uncertain"
  const openForDecision =
    candidate.decision === "pending" || candidate.decision === "conflict"
  const empty = !candidate.extracted_text.trim()

  return (
    <Card
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
            {uncertain ? (
              <Badge
                variant="outline"
                className="border-orange-400 text-orange-700 dark:text-orange-300"
              >
                Unsicher — Prüfung nötig
              </Badge>
            ) : (
              <Badge variant="outline" className="text-muted-foreground">
                Erkannt
              </Badge>
            )}
            {candidate.source_location && (
              <span className="text-xs text-muted-foreground">
                Fundstelle: {candidate.source_location}
              </span>
            )}
          </div>
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
              {DECISION_LABELS[candidate.decision]}
            </span>
          )}
        </div>

        {openForDecision && (
          <div className="flex shrink-0 flex-wrap items-center justify-end gap-2">
            <Button
              size="sm"
              disabled={busy || empty || !canAccept}
              title={
                empty
                  ? "Dieser Kandidat enthält keinen Text."
                  : !canAccept
                    ? "Zuerst Analyse starten."
                    : undefined
              }
              onClick={() => onDecide("accepted")}
            >
              Übernehmen
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={busy}
              onClick={() => onDecide("saved_as_source")}
            >
              Als Quelle speichern
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
        Textauszug {empty ? "(leer)" : ""}
      </button>
      {expanded && (
        <div className="border-t border-border bg-accent/20 px-4 py-3">
          {empty ? (
            <p className="text-xs text-muted-foreground">
              Für dieses Feld wurde kein Inhalt gefunden — es bleibt zur
              manuellen Bearbeitung offen.
            </p>
          ) : (
            <pre className="max-h-64 overflow-auto whitespace-pre-wrap text-xs text-foreground">
              {candidate.extracted_text}
            </pre>
          )}
        </div>
      )}
    </Card>
  )
}
