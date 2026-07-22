import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react"
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

  it("sends the inherited project data class when adding a text source (no forced question)", async () => {
    const onAddTextSource = vi.fn()
    render(
      <SourceTable
        sources={[]}
        controlled
        defaultDataClass="confidential"
        onAddTextSource={onAddTextSource}
      />
    )

    fireEvent.click(screen.getByRole("button", { name: "Text einfügen" }))
    // Die wirksame (geerbte) Einstufung ist sichtbar; die Stufenwahl selbst
    // ist optional eingeklappt («Abweichende Einstufung»).
    expect(
      screen.getByText(/Einstufung dieser Quelle:/)
    ).toBeInTheDocument()
    expect(screen.getByText(/wie im Projekt festgelegt/)).toBeInTheDocument()
    // Der Hinweistext erscheint erst nach dem Aufklappen.
    fireEvent.click(
      screen.getByRole("button", { name: "Abweichende Einstufung (optional)" })
    )
    expect(
      await screen.findByText(
        "Bitte wählen Sie die Vertraulichkeitsstufe dieser Quelle. Wenn Sie unsicher sind, wählen Sie Vertraulich. Die restriktivere Einstufung von Projekt und Quelle gilt."
      )
    ).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText("Titel der Quelle"), {
      target: { value: "Partnernotiz" },
    })
    fireEvent.change(screen.getByLabelText("Textinhalt"), {
      target: { value: "Gesprächsnotiz" },
    })
    fireEvent.click(screen.getByRole("button", { name: "Als Quelle hinzufügen" }))

    await waitFor(() => {
      expect(onAddTextSource).toHaveBeenCalledWith({
        title: "Partnernotiz",
        text: "Gesprächsnotiz",
        dataClass: "confidential",
      })
    })
  })

  it("inherits a public project class without opening the override", async () => {
    const onAddTextSource = vi.fn()
    render(
      <SourceTable
        sources={[]}
        controlled
        defaultDataClass="public"
        onAddTextSource={onAddTextSource}
      />
    )

    fireEvent.click(screen.getByRole("button", { name: "Text einfügen" }))
    fireEvent.change(screen.getByLabelText("Titel der Quelle"), {
      target: { value: "Notiz" },
    })
    fireEvent.change(screen.getByLabelText("Textinhalt"), {
      target: { value: "Inhalt" },
    })
    fireEvent.click(screen.getByRole("button", { name: "Als Quelle hinzufügen" }))

    await waitFor(() => {
      expect(onAddTextSource).toHaveBeenCalledWith({
        title: "Notiz",
        text: "Inhalt",
        dataClass: "public",
      })
    })
  })

  it("confirms file upload with the inherited data class", async () => {
    const onUploadFiles = vi.fn()
    const { container } = render(
      <SourceTable
        sources={[]}
        controlled
        defaultDataClass="internal"
        onUploadFiles={onUploadFiles}
      />
    )
    const input = container.querySelector('input[type="file"]') as HTMLInputElement
    const file = new File(["hello"], "a.txt", { type: "text/plain" })

    fireEvent.change(input, { target: { files: [file] } })
    await screen.findByRole("dialog", { name: "Datei hochladen" })
    fireEvent.click(screen.getByRole("button", { name: "Hochladen" }))

    await waitFor(() => {
      // Drittes Argument: der echte Byte-Fortschritts-Callback des Dialogs.
      expect(onUploadFiles).toHaveBeenCalledWith(
        [file],
        "internal",
        expect.any(Function)
      )
    })
    // Erfolg: Phase «Gespeichert» ist sichtbar, bevor der Dialog schliesst.
    expect(screen.getByText(/Gespeichert — der Text wird jetzt extrahiert/)).toBeInTheDocument()
  })

  it("keeps the file on upload error and shows retry + technical details", async () => {
    class FakeSourceError extends Error {
      readonly status = 413
      readonly code = "too_many_files"
      readonly correlationId = "corr-77"
    }
    const onUploadFiles = vi
      .fn()
      .mockRejectedValueOnce(new FakeSourceError("Zu viele Dateien in einem Vorgang."))
      .mockResolvedValueOnce(undefined)
    const { container } = render(
      <SourceTable
        sources={[]}
        controlled
        defaultDataClass="internal"
        onUploadFiles={onUploadFiles}
      />
    )
    const input = container.querySelector('input[type="file"]') as HTMLInputElement
    const file = new File(["hello"], "a.txt", { type: "text/plain" })

    fireEvent.change(input, { target: { files: [file] } })
    const dialog = await screen.findByRole("dialog", { name: "Datei hochladen" })
    fireEvent.click(screen.getByRole("button", { name: "Hochladen" }))

    // Ursachen-spezifische Meldung + Dialog bleibt offen, Datei erhalten.
    expect(
      await screen.findByText(/Zu viele Dateien in einem Vorgang/)
    ).toBeInTheDocument()
    expect(dialog).toBeInTheDocument()
    expect(screen.getByText("a.txt")).toBeInTheDocument()

    // Technische Details: Fehlercode + Correlation-ID nur eingeklappt.
    fireEvent.click(screen.getByRole("button", { name: "Technische Details" }))
    expect(await screen.findByText("too_many_files")).toBeInTheDocument()
    expect(screen.getByText("corr-77")).toBeInTheDocument()

    // «Erneut versuchen» stösst den Upload mit derselben Datei erneut an.
    fireEvent.click(screen.getByRole("button", { name: "Erneut versuchen" }))
    await waitFor(() => {
      expect(onUploadFiles).toHaveBeenCalledTimes(2)
    })
    expect(onUploadFiles.mock.calls[1][0]).toEqual([file])
  })

  it("RUN 4A: gruppiert Quellen nach Zweck, wenn Gruppendaten vorliegen", () => {
    render(
      <SourceTable
        sources={rows}
        controlled
        sourceGroups={
          new Map([
            ["1", "primary_application"],
            ["2", "project_documents"],
            ["3", "project_documents"],
            ["4", "public_research"],
          ])
        }
        primaryApplicationStatus="configured"
      />
    )
    const groups = screen.getByTestId("source-groups")
    expect(within(groups).getByText("Primärer Innolink-Antrag")).toBeInTheDocument()
    expect(within(groups).getByText("Projektunterlagen")).toBeInTheDocument()
    expect(within(groups).getByText("Öffentliche Recherche")).toBeInTheDocument()
    // Zweck-Sätze der Gruppen sind sichtbar.
    expect(
      within(groups).getByText("Verwendet für Import und Antragsanalyse.")
    ).toBeInTheDocument()
    expect(
      within(groups).getByText("Verwendet für Markt- und Konkurrenzvergleich.")
    ).toBeInTheDocument()
    // Die Quellen liegen in ihren Gruppen.
    expect(
      within(screen.getByTestId("source-group-primary_application")).getByText(
        "a.pdf"
      )
    ).toBeInTheDocument()
    expect(
      within(screen.getByTestId("source-group-public_research")).getByText(
        "d.txt"
      )
    ).toBeInTheDocument()
  })

  it("RUN 4A: ohne Primärantrag erscheint ein freundlicher Hinweis statt einer leeren Gruppe", () => {
    render(
      <SourceTable
        sources={rows.slice(1)}
        controlled
        sourceGroups={
          new Map([
            ["2", "project_documents"],
            ["3", "project_documents"],
            ["4", "public_research"],
          ])
        }
        primaryApplicationStatus="not_configured"
      />
    )
    expect(
      screen.getByText(/Noch kein primärer Innolink-Antrag festgelegt/)
    ).toBeInTheDocument()
  })

  it("RUN 4A: ohne Gruppendaten bleibt die flache Liste (Mock-Modus) erhalten", () => {
    render(<SourceTable sources={rows} controlled />)
    expect(screen.queryByTestId("source-groups")).toBeNull()
    expect(screen.getByText("a.pdf")).toBeInTheDocument()
  })
})
