import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
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
  it("renders every contract status and the hints", () => {
    render(<SourceTable sources={rows} controlled />)
    expect(screen.getByText("Verarbeitet")).toBeInTheDocument()
    expect(screen.getByText("In Verarbeitung")).toBeInTheDocument()
    expect(screen.getByText("Manuelle Prüfung nötig")).toBeInTheDocument()
    expect(screen.getByText("Fehler")).toBeInTheDocument()
    expect(screen.getByText("Kein durchsuchbarer Text")).toBeInTheDocument()
    expect(screen.getByText("Verarbeitung fehlgeschlagen")).toBeInTheDocument()
  })

  it("confirms deletion via the live handler", () => {
    const onDeleteSource = vi.fn()
    render(<SourceTable sources={rows} controlled onDeleteSource={onDeleteSource} />)
    fireEvent.click(screen.getByLabelText("a.pdf entfernen"))
    fireEvent.click(screen.getByRole("button", { name: "Entfernen" }))
    expect(onDeleteSource).toHaveBeenCalledWith("1")
  })
})
