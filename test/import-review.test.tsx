// R3.3 — Import-Review: Entscheidungsaktionen, Unsicher-Markierung ohne
// Vorauswahl, Konflikt-Bestätigung, kein Auto-Accept.
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { ImportReview } from "@/components/import/import-review"
import type { ImportCandidateDto } from "@/lib/imports"

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

const listProjectRuns = vi.fn(async () => [
  { run_id: "run-1", project_id: "p-1", status: "completed" },
])
vi.mock("@/lib/runs", () => ({
  listProjectRuns: (...args: unknown[]) => listProjectRuns(...args),
  createRun: vi.fn(),
  getRun: vi.fn(),
}))

vi.mock("@/lib/sources", () => ({
  uploadFiles: vi.fn(),
  getSource: vi.fn(),
}))

const getImportCandidates = vi.fn<() => Promise<ImportCandidateDto[]>>()
const decideImportCandidate = vi.fn()
const createImportCandidates = vi.fn()

vi.mock("@/lib/imports", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/imports")>()
  return {
    ...actual,
    getImportCandidates: (...args: unknown[]) => getImportCandidates(...args),
    decideImportCandidate: (...args: unknown[]) =>
      decideImportCandidate(...args),
    createImportCandidates: (...args: unknown[]) =>
      createImportCandidates(...args),
  }
})

import { ImportError } from "@/lib/imports"

function candidate(
  overrides: Partial<ImportCandidateDto> = {}
): ImportCandidateDto {
  return {
    import_candidate_id: "c-abstract",
    source_id: "s-1",
    field_id: "INTRO.APP.ABSTRACT",
    label: "Abstract (wird in Aramis publiziert)",
    extracted_text: "Das Projekt entwickelt eine adaptive Lastprognose.",
    confidence: "found",
    source_location: "Seite 1",
    decision: "pending",
    decided_at: null,
    accepted_draft_version_id: null,
    ...overrides,
  }
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

beforeEach(() => {
  getImportCandidates.mockResolvedValue(FIXTURE)
  decideImportCandidate.mockImplementation(
    async (_id: string, payload: { decision: string }) =>
      candidate({ decision: payload.decision as ImportCandidateDto["decision"] })
  )
})

afterEach(() => {
  vi.clearAllMocks()
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
    expect(within(rows[0]).getByText(/Fundstelle: Seite 1/)).toBeInTheDocument()
    // Unsicher ist visuell markiert …
    expect(
      within(rows[1]).getByText("Unsicher — Prüfung nötig")
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
})

describe("ImportReview — Entscheidungsaktionen", () => {
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

  it("Als Quelle speichern und Ignorieren senden die jeweilige Entscheidung", async () => {
    await renderReview()
    const row = screen.getAllByTestId("import-candidate")[0]
    fireEvent.click(
      within(row).getByRole("button", { name: "Als Quelle speichern" })
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

  it("ohne abgeschlossene Analyse ist Übernehmen gesperrt und der Start angeboten", async () => {
    listProjectRuns.mockResolvedValueOnce([])
    await renderReview()
    expect(screen.getByTestId("import-start-run")).toBeInTheDocument()
    const row = screen.getAllByTestId("import-candidate")[0]
    expect(
      within(row).getByRole("button", { name: "Übernehmen" })
    ).toBeDisabled()
  })

  it("führt nach den Entscheidungen zur Fix Queue («Nächste Aufgaben»)", async () => {
    await renderReview()
    fireEvent.click(screen.getByTestId("import-to-fix-queue"))
    expect(push).toHaveBeenCalledWith("/review")
  })
})
