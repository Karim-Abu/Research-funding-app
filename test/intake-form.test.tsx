// Intake-Vereinfachung: ein Projekteinstieg — Idee und/oder Upload, Default
// «Vertraulich» mit kompaktem «Ändern», keine Partner-/Budget-Doppelerfassung,
// «Später fortsetzen» = echte serverseitige Anlage (status draft).
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { http, HttpResponse } from "msw"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { AppProviders } from "@/components/providers/app-providers"
import {
  IntakeForm,
  INTAKE_DESCRIPTION_PLACEHOLDER,
} from "@/components/intake/intake-form"
import { setBackendMode } from "@/lib/app-mode"
import { UPLOAD_HINT_KEY } from "@/lib/sources"
import { server } from "./server"

// jsdom lacks Element.scrollTo, which the intake form calls on mount.
if (typeof Element.prototype.scrollTo !== "function") {
  Element.prototype.scrollTo = () => {}
}

const push = vi.fn()
const replace = vi.fn()

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace }),
  usePathname: () => "/intake",
}))

const SESSION = {
  user: {
    user_id: "user-anna",
    name: "Anna Keller",
    email: "anna.keller@example.test",
    effective_role: "lead_admin",
    display_label: "Anna Keller",
  },
  csrf_token: "tok",
}

function projectBody(payload: Record<string, unknown> = {}) {
  const now = new Date().toISOString()
  return {
    project_id: "p-1",
    workspace_id: "ws",
    title: "Testprojekt",
    description: "Idee",
    funding_instrument_profile_id: "f",
    data_classification: {
      sensitivity: "confidential",
      origin: "real_project",
      processing_mode: "local_only",
      web_research_mode: "off",
      nda_applies: false,
    },
    status: "draft",
    created_at: now,
    updated_at: now,
    active_run_id: null,
    ...payload,
  }
}

function sourceDoc(sourceId: string, type: string, name: string) {
  return {
    source_id: sourceId,
    project_id: "p-1",
    name,
    type,
    status: "uploaded",
    data_classification: projectBody().data_classification,
  }
}

function renderForm() {
  return render(
    <AppProviders mode="live">
      <IntakeForm />
    </AppProviders>
  )
}

function fillIdea() {
  fireEvent.change(screen.getByLabelText(/Projekttitel/), {
    target: { value: "Testprojekt" },
  })
  fireEvent.change(screen.getByRole("textbox", { name: /Projektidee/ }), {
    target: { value: "Eine Projektidee." },
  })
}

function addFile(name: string, type = "text/plain") {
  const input = screen.getByTestId("intake-file-input")
  fireEvent.change(input, {
    target: { files: [new File(["Inhalt"], name, { type })] },
  })
}

function submit() {
  fireEvent.click(
    screen.getByRole("button", { name: "Projekt erstellen und weiter" })
  )
}

describe("IntakeForm — ein Projekteinstieg", () => {
  let projectPayloads: Array<Record<string, unknown>>
  let uploadCount: number

  beforeEach(() => {
    push.mockReset()
    replace.mockReset()
    window.sessionStorage.clear()
    projectPayloads = []
    uploadCount = 0
    server.use(
      http.get("/api/session", () => HttpResponse.json(SESSION)),
      http.post("/api/projects", async ({ request }) => {
        const payload = (await request.json()) as Record<string, unknown>
        projectPayloads.push(payload)
        return HttpResponse.json(
          projectBody({
            title: payload.title,
            description: payload.description,
          }),
          { status: 201 }
        )
      }),
      http.post("/api/projects/p-1/sources/files", () => {
        uploadCount += 1
        return HttpResponse.json([sourceDoc("src-1", "txt", "notizen.txt")], {
          status: 201,
        })
      })
    )
  })
  afterEach(() => setBackendMode("mock"))

  it("Start nur mit Projektidee: Default «Vertraulich», keine Partner-POSTs, weiter zu /quellen", async () => {
    renderForm()
    fillIdea()
    submit()

    await waitFor(() => expect(push).toHaveBeenCalledWith("/quellen"))
    expect(projectPayloads).toHaveLength(1)
    expect(projectPayloads[0]).toMatchObject({
      title: "Testprojekt",
      description: "Eine Projektidee.",
    })
    const classification = projectPayloads[0].data_classification as {
      sensitivity: string
    }
    expect(classification.sensitivity).toBe("confidential")
    // Ohne Dateien wird nichts hochgeladen.
    expect(uploadCount).toBe(0)
  })

  it("«Ändern» öffnet die Stufenwahl; Öffentlich → Payload public", async () => {
    renderForm()
    fillIdea()
    fireEvent.click(screen.getByRole("button", { name: "Ändern" }))
    const dialog = await screen.findByRole("dialog")
    // «Öffentlich» präzise ankern — die Intern-Karte enthält «Öffentlichkeit».
    fireEvent.click(
      screen.getByRole("radio", { name: /^Öffentlich Keine internen/ })
    )
    fireEvent.click(screen.getByRole("button", { name: "Fertig" }))
    await waitFor(() => expect(dialog).not.toBeInTheDocument())
    submit()

    await waitFor(() => expect(push).toHaveBeenCalledWith("/quellen"))
    const classification = projectPayloads[0].data_classification as {
      sensitivity: string
    }
    expect(classification.sensitivity).toBe("public")
  })

  it("Start nur mit Datei (.txt): Titel-Prefill, Platzhalter-Beschreibung, Upload, /quellen", async () => {
    renderForm()
    addFile("notizen.txt")
    // Titel aus dem Dateinamen vorbelegt und editierbar.
    expect(screen.getByLabelText(/Projekttitel/)).toHaveValue("notizen")
    submit()

    await waitFor(() => expect(push).toHaveBeenCalledWith("/quellen"))
    expect(projectPayloads[0]).toMatchObject({
      title: "notizen",
      description: INTAKE_DESCRIPTION_PLACEHOLDER,
    })
    expect(uploadCount).toBe(1)
  })

  it("Start nur mit Innolink-PDF: weiter zur Felderkennung (/import?source=…)", async () => {
    server.use(
      http.post("/api/projects/p-1/sources/files", () => {
        uploadCount += 1
        return HttpResponse.json(
          [sourceDoc("src-1", "pdf", "innolink_sample.pdf")],
          { status: 201 }
        )
      })
    )
    renderForm()
    addFile("innolink_sample.pdf", "application/pdf")
    expect(
      screen.getByText(/Innolink-PDF erkannt/)
    ).toBeInTheDocument()
    submit()

    await waitFor(() =>
      expect(push).toHaveBeenCalledWith("/import?source=src-1")
    )
    expect(projectPayloads[0]).toMatchObject({
      title: "innolink_sample",
      description: INTAKE_DESCRIPTION_PLACEHOLDER,
    })
  })

  it("Start mit Idee UND Datei: description = getippte Idee, nicht der Platzhalter", async () => {
    renderForm()
    fillIdea()
    addFile("notizen.txt")
    // Titel-Prefill überschreibt eine vorhandene Eingabe nicht.
    expect(screen.getByLabelText(/Projekttitel/)).toHaveValue("Testprojekt")
    submit()

    await waitFor(() => expect(push).toHaveBeenCalledWith("/quellen"))
    expect(projectPayloads[0]).toMatchObject({
      description: "Eine Projektidee.",
    })
  })

  it("leeres Formular: beide Aktionen deaktiviert, Hinweis erklärt die Minimalangabe", () => {
    renderForm()
    expect(
      screen.getByRole("button", { name: "Projekt erstellen und weiter" })
    ).toBeDisabled()
    expect(
      screen.getByRole("button", { name: "Später fortsetzen" })
    ).toBeDisabled()
    expect(
      screen.getByText(
        /Noch offen: Projekttitel und kurze Projektidee — oder laden Sie eine Datei hoch\./
      )
    ).toBeInTheDocument()
  })

  it("«Später fortsetzen» legt das Projekt serverseitig an und führt zur Übersicht", async () => {
    renderForm()
    fillIdea()
    fireEvent.click(screen.getByRole("button", { name: "Später fortsetzen" }))

    await waitFor(() => expect(push).toHaveBeenCalledWith("/"))
    expect(projectPayloads).toHaveLength(1)
  })

  it("Upload-Fehler nach Anlage: Projekt bleibt, Hinweis-Flag gesetzt, weiter zu /quellen", async () => {
    server.use(
      http.post("/api/projects/p-1/sources/files", () =>
        HttpResponse.json({ code: "error" }, { status: 500 })
      )
    )
    renderForm()
    addFile("notizen.txt")
    submit()

    await waitFor(() => expect(push).toHaveBeenCalledWith("/quellen"))
    expect(projectPayloads).toHaveLength(1)
    expect(window.sessionStorage.getItem(UPLOAD_HINT_KEY)).toBe("1")
  })

  it("Partner- und Budget-Eingaben sind im Intake nicht mehr erreichbar", () => {
    renderForm()
    expect(
      screen.queryByRole("button", { name: "Partner hinzufügen" })
    ).toBeNull()
    expect(screen.queryByLabelText("Partnername")).toBeNull()
    expect(screen.queryByLabelText(/Budgetrahmen/)).toBeNull()
    expect(
      screen.getByText("Partner und Budget ergänzen Sie im nächsten Schritt.")
    ).toBeInTheDocument()
  })
})
