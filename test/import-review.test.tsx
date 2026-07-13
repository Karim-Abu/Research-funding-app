// R3.3 — Import-Review: Entscheidungsaktionen, Unsicher-Markierung ohne
// Vorauswahl, Konflikt-Bestätigung, kein Auto-Accept.
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { ImportReview } from "@/components/import/import-review"
import type {
  ImportCandidateDto,
  StructuredImportCandidateDto,
} from "@/lib/imports"

const push = vi.fn()

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace: vi.fn() }),
  usePathname: () => "/import",
}))

vi.mock("@/lib/intake-store", () => ({
  getActiveProjectId: () => "p-1",
}))

vi.mock("@/lib/projects", () => ({
  getProject: vi.fn(async () => ({
    project_id: "p-1",
    data_classification: {
      sensitivity: "public",
      origin: "synthetic",
      processing_mode: "deterministic_only",
      web_research_mode: "off",
      nda_applies: false,
    },
  })),
}))

// Zentrale Run-Auswahl (Ladder): der Test steuert den aktiven Run direkt.
let activeRunId: string | null = "run-1"
vi.mock("@/components/providers/workflow-run-provider", () => ({
  useActiveRun: () => ({
    runId: activeRunId,
    source: activeRunId ? "project_active" : null,
    loading: false,
    reload: vi.fn(),
  }),
}))

const getSource = vi.fn()
const uploadFiles = vi.fn()
vi.mock("@/lib/sources", () => ({
  uploadFiles: (...args: unknown[]) => uploadFiles(...args),
  getSource: (...args: unknown[]) => getSource(...args),
}))

const getImportCandidates = vi.fn<() => Promise<ImportCandidateDto[]>>()
const getStructuredImportCandidates = vi.fn<
  () => Promise<StructuredImportCandidateDto[]>
>()
const decideImportCandidate = vi.fn()
const decideStructuredImportCandidate = vi.fn()
const createImportCandidates = vi.fn()

vi.mock("@/lib/imports", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/imports")>()
  return {
    ...actual,
    getImportCandidates: (...args: unknown[]) => getImportCandidates(...args),
    getStructuredImportCandidates: (...args: unknown[]) =>
      getStructuredImportCandidates(...args),
    decideImportCandidate: (...args: unknown[]) =>
      decideImportCandidate(...args),
    decideStructuredImportCandidate: (...args: unknown[]) =>
      decideStructuredImportCandidate(...args),
    createImportCandidates: (...args: unknown[]) =>
      createImportCandidates(...args),
  }
})

import { ImportError } from "@/lib/imports"

function candidate(
  overrides: Partial<ImportCandidateDto> = {}
): ImportCandidateDto {
  const value: ImportCandidateDto = {
    import_candidate_id: "c-abstract",
    source_id: "s-1",
    field_id: "INTRO.APP.ABSTRACT",
    label: "Abstract (wird in Aramis publiziert)",
    extracted_text: "Das Projekt entwickelt eine adaptive Lastprognose.",
    edited_text: null,
    confidence: "found",
    source_location: "Seite 1",
    mapping_version: "innolink-narrative-v2",
    mapping_status: "content_detected",
    section_metadata: [],
    decision: "pending",
    decided_at: null,
    accepted_draft_version_id: null,
    ...overrides,
  }
  value.mapping_status =
    overrides.mapping_status ??
    (!value.extracted_text ? "empty" : value.confidence === "uncertain" ? "uncertain" : "content_detected")
  value.section_metadata = overrides.section_metadata ?? [
    {
      target_sections: [value.label],
      source_location: value.source_location,
      status: value.mapping_status,
      candidate_text: value.extracted_text,
      original_excerpt: `Abstract\n${value.extracted_text}`.trim(),
      migration_version: null,
      requires_manual_assignment: false,
      review_note: null,
    },
  ]
  return value
}

const FIXTURE: ImportCandidateDto[] = [
  candidate(),
  candidate({
    import_candidate_id: "c-name-en",
    field_id: "INTRO.APP.NAME_EN",
    label: "Projekttitel (Englisch)",
    extracted_text: "",
    confidence: "uncertain",
  }),
]

function structuredCandidate(
  overrides: Partial<StructuredImportCandidateDto> = {}
): StructuredImportCandidateDto {
  return {
    candidate_id: "sc-budget",
    source_id: "s-1",
    candidate_kind: "budget",
    target_key: "project.cash_contribution",
    label: "Barbeitrag",
    payload_json: { cash_contribution: 20000 },
    edited_payload_json: null,
    effective_payload_json: { cash_contribution: 20000 },
    confidence: "found",
    source_location: "Seite 6",
    mapping_version: "innolink-structured-v1",
    decision: "pending",
    decided_at: null,
    applied_resource_id: null,
    current_value_json: { cash_contribution: 5000 },
    has_conflict: true,
    conflict_reason: "existing_project_value",
    requires_manual_edit: false,
    ...overrides,
  }
}

beforeEach(() => {
  activeRunId = "run-1"
  getImportCandidates.mockResolvedValue(FIXTURE)
  getStructuredImportCandidates.mockResolvedValue([])
  decideImportCandidate.mockImplementation(
    async (_id: string, payload: { decision: string; edited_text?: string }) =>
      candidate({
        decision: payload.decision as ImportCandidateDto["decision"],
        edited_text: payload.edited_text ?? null,
      })
  )
  decideStructuredImportCandidate.mockImplementation(
    async (
      _id: string,
      payload: {
        decision: string
        edited_payload_json?: Record<string, unknown>
      }
    ) =>
      structuredCandidate({
        decision:
          payload.decision as StructuredImportCandidateDto["decision"],
        edited_payload_json: payload.edited_payload_json ?? null,
      })
  )
})

afterEach(() => {
  vi.clearAllMocks()
  window.history.pushState({}, "", "/import")
})

async function renderReview() {
  render(<ImportReview />)
  await waitFor(() =>
    expect(screen.getByTestId("import-review")).toBeInTheDocument()
  )
}

describe("ImportReview — Darstellung", () => {
  it("zeigt Kandidaten mit Label, Fundstelle und Unsicher-Markierung ohne Vorauswahl", async () => {
    await renderReview()
    const rows = screen.getAllByTestId("import-candidate")
    expect(rows).toHaveLength(2)
    expect(
      within(rows[0]).getByText("Abstract (wird in Aramis publiziert)")
    ).toBeInTheDocument()
    expect(within(rows[0]).getByText(/Fundseite: Seite 1/)).toBeInTheDocument()
    // Unsicher ist visuell markiert …
    expect(
      within(rows[1]).getByText("Leer")
    ).toBeInTheDocument()
    // … und nichts ist vorentschieden.
    expect(screen.queryByText("Übernommen")).not.toBeInTheDocument()
    expect(screen.queryByText("Ignoriert")).not.toBeInTheDocument()
  })

  it("übernimmt nichts automatisch — auch bei hoher Konfidenz", async () => {
    await renderReview()
    expect(decideImportCandidate).not.toHaveBeenCalled()
  })

  it("deaktiviert Übernehmen für leere Kandidaten", async () => {
    await renderReview()
    const uncertainRow = screen.getAllByTestId("import-candidate")[1]
    expect(
      within(uncertainRow).getByRole("button", { name: "Übernehmen" })
    ).toBeDisabled()
  })

  it("zeigt Zielabschnitt, Originalausschnitt und technische Daten getrennt", async () => {
    await renderReview()
    const row = screen.getAllByTestId("import-candidate")[0]
    expect(within(row).getByText(/Zielabschnitt:/)).toBeInTheDocument()
    fireEvent.click(
      within(row).getByRole("button", { name: "Abschnittsdetails" })
    )
    expect(within(row).getByText("Originalausschnitt")).toBeInTheDocument()
    expect(within(row).getByText("Technische Details")).toBeInTheDocument()
    expect(within(row).getByText("innolink-narrative-v2")).toBeInTheDocument()
  })

  it("verlangt für die gemeinsame 4.5.2/4.5.3-Altzuordnung Bearbeitung", async () => {
    getImportCandidates.mockResolvedValueOnce([
      candidate({
        import_candidate_id: "c-sol",
        field_id: "SOL.INNOVATION_SOLUTION.EDITOR",
        label: "Innovation & Lösung",
        extracted_text: "4.1\nSynthetische Antwort.",
        confidence: "uncertain",
        mapping_status: "legacy_migrated",
        section_metadata: [
          {
            target_sections: ["4.5.2", "4.5.3"],
            source_location: "Seite 3",
            status: "uncertain",
            candidate_text: "Nein",
            original_excerpt: "Alte Lizenzfrage\nNein",
            migration_version: "innolink-intro-ip-to-solution-v1",
            requires_manual_assignment: true,
            review_note: "Fachlich zuordnen.",
          },
        ],
      }),
    ])
    await renderReview()
    const row = screen.getByTestId("import-candidate")
    expect(within(row).getByText("Altstruktur migriert")).toBeInTheDocument()
    expect(within(row).getByText(/4.5.2, 4.5.3/)).toBeInTheDocument()
    expect(within(row).getByRole("button", { name: "Übernehmen" })).toBeDisabled()
    fireEvent.click(
      within(row).getByRole("button", { name: "Bearbeiten & übernehmen" })
    )
    expect(
      await screen.findByText(/keine FTO- oder IP-Schlussfolgerung/)
    ).toBeInTheDocument()
  })
})

describe("ImportReview — Entscheidungsaktionen", () => {
  it("gruppiert strukturierte Werte, zeigt Altwert und bestätigt Konflikte explizit", async () => {
    getStructuredImportCandidates.mockResolvedValueOnce([structuredCandidate()])
    decideStructuredImportCandidate
      .mockRejectedValueOnce(
        new ImportError(409, "structured_import_conflict", "Wert vorhanden.")
      )
      .mockResolvedValueOnce(structuredCandidate({ decision: "accepted" }))
    await renderReview()

    const section = screen.getByTestId("structured-import-review")
    expect(within(section).getByText("Budget")).toBeInTheDocument()
    const row = within(section).getByTestId("structured-import-candidate")
    expect(within(row).getByText("Fundseite: Seite 6")).toBeInTheDocument()
    expect(within(row).getByText("Aktueller Wert")).toBeInTheDocument()
    fireEvent.click(within(row).getByRole("button", { name: "Übernehmen" }))

    const confirm = await screen.findByTestId(
      "structured-import-confirm-overwrite"
    )
    fireEvent.click(confirm)
    await waitFor(() =>
      expect(decideStructuredImportCandidate).toHaveBeenLastCalledWith(
        "sc-budget",
        {
          decision: "accepted",
          edited_payload_json: { cash_contribution: 20000 },
          confirm_overwrite: true,
        }
      )
    )
  })

  it("zeigt Vertreter nur eingeklappt und ohne Kontaktfelder", async () => {
    getImportCandidates.mockResolvedValueOnce([])
    getStructuredImportCandidates.mockResolvedValueOnce([
      structuredCandidate({
        candidate_id: "sc-partner",
        candidate_kind: "partner",
        target_key: "partner.research.01",
        label: "Forschungspartner",
        payload_json: {
          name: "Synthetisches Labor",
          partner_type: "research_partner",
          official_representative: { display_name: "Robin Example" },
        },
        effective_payload_json: {
          name: "Synthetisches Labor",
          partner_type: "research_partner",
          official_representative: { display_name: "Robin Example" },
        },
        current_value_json: null,
        has_conflict: false,
        conflict_reason: null,
      }),
    ])
    await renderReview()
    const disclosure = screen.getByText(
      "Personenangabe zur offiziellen Vertretung prüfen"
    )
    expect(disclosure.closest("details")).not.toHaveAttribute("open")
    fireEvent.click(disclosure)
    expect(await screen.findByText("Robin Example")).toBeInTheDocument()
    expect(screen.getByText(/keine E-Mail-Adresse/)).toBeInTheDocument()
  })

  it("Übernehmen ruft die Entscheidung mit run_id auf und zeigt den neuen Zustand", async () => {
    await renderReview()
    const row = screen.getAllByTestId("import-candidate")[0]
    fireEvent.click(within(row).getByRole("button", { name: "Übernehmen" }))
    await waitFor(() =>
      expect(decideImportCandidate).toHaveBeenCalledWith("c-abstract", {
        decision: "accepted",
        run_id: "run-1",
      })
    )
    expect(await screen.findByText("Übernommen")).toBeInTheDocument()
  })

  it("Hintergrund verknüpfen und Ignorieren senden die bestehende Entscheidung", async () => {
    await renderReview()
    const row = screen.getAllByTestId("import-candidate")[0]
    fireEvent.click(
      within(row).getByRole("button", { name: "Nur als Hintergrund verknüpfen" })
    )
    await waitFor(() =>
      expect(decideImportCandidate).toHaveBeenCalledWith("c-abstract", {
        decision: "saved_as_source",
      })
    )
    const uncertainRow = screen.getAllByTestId("import-candidate")[1]
    fireEvent.click(
      within(uncertainRow).getByRole("button", { name: "Ignorieren" })
    )
    await waitFor(() =>
      expect(decideImportCandidate).toHaveBeenCalledWith("c-name-en", {
        decision: "ignored",
      })
    )
  })

  it("Konflikt verlangt eine explizite Bestätigung (confirm_overwrite)", async () => {
    decideImportCandidate
      .mockRejectedValueOnce(
        new ImportError(409, "import_conflict", "Bearbeiteter Entwurf vorhanden.")
      )
      .mockResolvedValueOnce(candidate({ decision: "accepted" }))
    await renderReview()
    const row = screen.getAllByTestId("import-candidate")[0]
    fireEvent.click(within(row).getByRole("button", { name: "Übernehmen" }))

    // Dialog erscheint; erst die Bestätigung löst die Überschreibung aus.
    const confirm = await screen.findByTestId("import-confirm-overwrite")
    expect(decideImportCandidate).toHaveBeenCalledTimes(1)
    fireEvent.click(confirm)
    await waitFor(() =>
      expect(decideImportCandidate).toHaveBeenLastCalledWith("c-abstract", {
        decision: "accepted",
        run_id: "run-1",
        confirm_overwrite: true,
      })
    )
  })

  it("Übernehmen funktioniert OHNE Analyse-Lauf (Vormerkung, kein run_id)", async () => {
    // Fachliche Korrektur: kein «Zuerst Analyse starten»-Gate mehr.
    activeRunId = null
    await renderReview()
    expect(screen.queryByTestId("import-start-run")).not.toBeInTheDocument()
    expect(
      screen.getByText(/fliessen beim nächsten Analyse-Lauf als/)
    ).toBeInTheDocument()
    const row = screen.getAllByTestId("import-candidate")[0]
    const accept = within(row).getByRole("button", { name: "Übernehmen" })
    expect(accept).toBeEnabled()
    fireEvent.click(accept)
    await waitFor(() =>
      expect(decideImportCandidate).toHaveBeenCalledWith("c-abstract", {
        decision: "accepted",
      })
    )
    expect(await screen.findByText("Übernommen")).toBeInTheDocument()
  })

  it("Bearbeiten & übernehmen sendet edited_text und zeigt «Bearbeitet übernommen»", async () => {
    activeRunId = null
    await renderReview()
    const row = screen.getAllByTestId("import-candidate")[0]
    fireEvent.click(
      within(row).getByRole("button", { name: "Bearbeiten & übernehmen" })
    )
    const textarea = await screen.findByLabelText(
      "Text für die Übernahme bearbeiten"
    )
    // Vorbefüllt mit dem Originaltext; dann editieren.
    expect((textarea as HTMLTextAreaElement).value).toContain(
      "adaptive Lastprognose"
    )
    fireEvent.change(textarea, {
      target: { value: "Redigierte Fassung des Abstracts." },
    })
    fireEvent.click(screen.getByTestId("import-accept-edited"))
    await waitFor(() =>
      expect(decideImportCandidate).toHaveBeenCalledWith("c-abstract", {
        decision: "accepted",
        edited_text: "Redigierte Fassung des Abstracts.",
      })
    )
    expect(await screen.findByText("Bearbeitet übernommen")).toBeInTheDocument()
  })

  it("Upload-Fehler: Datei bleibt für «Erneut versuchen» erhalten, Details zeigen die Correlation-ID", async () => {
    getImportCandidates.mockResolvedValueOnce([])
    class FakeSourceError extends Error {
      readonly status = 413
      readonly code = "too_many_files"
      readonly correlationId = "corr-import-9"
    }
    uploadFiles
      .mockRejectedValueOnce(new FakeSourceError("Zu viele Dateien in einem Vorgang."))
      .mockResolvedValueOnce([
        { source_id: "s-2", name: "a.pdf", status: "processed" },
      ])
    createImportCandidates.mockResolvedValueOnce(FIXTURE)

    render(<ImportReview />)
    const input = await screen.findByTestId("import-file-input")
    const file = new File(["x"], "a.pdf", { type: "application/pdf" })
    fireEvent.change(input, { target: { files: [file] } })

    // Ursachen-spezifische Meldung + Technische Details (Correlation-ID).
    expect(
      await screen.findByText("Zu viele Dateien in einem Vorgang.")
    ).toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: "Technische Details" }))
    expect(await screen.findByText("corr-import-9")).toBeInTheDocument()

    // Retry nutzt DIESELBE Datei erneut — kein erneutes Auswählen nötig.
    fireEvent.click(screen.getByRole("button", { name: "Erneut versuchen" }))
    await waitFor(() => expect(uploadFiles).toHaveBeenCalledTimes(2))
    expect(uploadFiles.mock.calls[1][1]).toEqual([file])
  })

  it("führt nach den Entscheidungen zur Fix Queue («Nächste Aufgaben»)", async () => {
    await renderReview()
    fireEvent.click(screen.getByTestId("import-to-fix-queue"))
    expect(push).toHaveBeenCalledWith("/review")
  })

  it("übernimmt eine im Intake hochgeladene Quelle (?source=…) ohne zweiten Upload", async () => {
    // Keine vorhandenen Kandidaten → der Adopt-Pfad greift.
    getImportCandidates.mockResolvedValueOnce([])
    getSource.mockResolvedValueOnce({
      source_id: "src-9",
      project_id: "p-1",
      name: "innolink_sample.pdf",
      type: "pdf",
      status: "processed",
    })
    createImportCandidates.mockResolvedValueOnce(FIXTURE)
    window.history.pushState({}, "", "/import?source=src-9")

    await renderReview()

    expect(getSource).toHaveBeenCalledWith("src-9")
    expect(createImportCandidates).toHaveBeenCalledTimes(1)
    expect(createImportCandidates).toHaveBeenCalledWith("p-1", "src-9")
    expect(screen.getAllByTestId("import-candidate")).toHaveLength(2)
  })
})
