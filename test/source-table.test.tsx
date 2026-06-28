import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import { SourceTable } from "@/components/quellen/source-table"
import type { Source } from "@/lib/quellen-mock-data"

const rows: Source[] = [
  { id: "1", name: "a.pdf", type: "PDF", status: "processed", addedBy: "-", addedAt: "-" },
  { id: "2", name: "b.docx", type: "DOCX", status: "processing", addedBy: "-", addedAt: "-" },
  {
    id: "3",
    name: "c.pdf",
    type: "PDF",
    status: "needs_manual_input",
    addedBy: "-",
    addedAt: "-",
    errorHint: "Kein durchsuchbarer Text",
  },
  {
    id: "4",
    name: "d.txt",
    type: "Text",
    status: "failed",
    addedBy: "-",
    addedAt: "-",
    errorHint: "Verarbeitung fehlgeschlagen",
  },
]

describe("SourceTable live statuses", () => {
  it("renders source ways, every status and the hints", () => {
    render(<SourceTable sources={rows} controlled />)
    expect(screen.getAllByText("Datei hochladen").length).toBeGreaterThan(0)
    expect(screen.getAllByText("URL hinzufügen").length).toBeGreaterThan(0)
    expect(screen.getAllByText("Text einfügen").length).toBeGreaterThan(0)
    expect(
      screen.getAllByText("Aus anderem Projekt übernehmen").length
    ).toBeGreaterThan(0)
    expect(screen.getByText("Verarbeitet")).toBeInTheDocument()
    expect(screen.getByText("In Verarbeitung")).toBeInTheDocument()
    expect(screen.getByText("Prüfung nötig")).toBeInTheDocument()
    expect(screen.getByText("Fehler")).toBeInTheDocument()
    expect(screen.getByText("Kein durchsuchbarer Text")).toBeInTheDocument()
    expect(screen.getByText("Verarbeitung fehlgeschlagen")).toBeInTheDocument()
    expect(screen.getAllByText("Format prüfen")).toHaveLength(2)
    expect(screen.getAllByText("Erneut hochladen")).toHaveLength(2)
    expect(screen.getAllByText("Quelle entfernen")).toHaveLength(2)
  })

  it("confirms deletion via the live handler", () => {
    const onDeleteSource = vi.fn()
    render(<SourceTable sources={rows} controlled onDeleteSource={onDeleteSource} />)
    fireEvent.click(screen.getByRole("button", { name: "a.pdf: Löschen" }))
    fireEvent.click(screen.getByRole("button", { name: "Entfernen" }))
    expect(onDeleteSource).toHaveBeenCalledWith("1")
  })

  it("adds a URL source in uncontrolled fallback mode", async () => {
    render(<SourceTable sources={[]} />)
    fireEvent.click(screen.getByRole("button", { name: "URL hinzufügen" }))
    fireEvent.change(screen.getByLabelText("URL"), {
      target: { value: "https://www.innosuisse.admin.ch/innovation-projects" },
    })
    fireEvent.click(screen.getByRole("button", { name: "Hinzufügen" }))
    await waitFor(() => {
      expect(
        screen.getByText("https://www.innosuisse.admin.ch/innovation-projects")
      ).toBeInTheDocument()
    })
    expect(screen.getByText("Ausstehend")).toBeInTheDocument()
  })
})
