// B1–B4 — editierbare Fokusansicht je Unterabschnitt eines Composite-Felds:
// Editor zeigt nur den Antwortbereich, Portalfrage als nicht editierbare
// Karte, Segment- und Gesamtzähler sichtbar, Abschnittswechsel verliert keine
// ungespeicherte Änderung, Degraded-Fallback bei veränderten Markern.
import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent, within } from "@testing-library/react"
import { http, HttpResponse } from "msw"
import { server } from "./server"

vi.mock(
  "@/components/editor/rich-text-editor",
  async () => await import("./mocks/rich-text-editor")
)

import { LiveEditor } from "@/components/editor/live-editor"

const VC = "VC.BUSINESS_TARGETS_MODEL.EDITOR"

const TEMPLATE_TEXT = [
  "3.1 Beschreiben Sie die Business-Ziele und das Geschäftsmodell",
  "Antwort zu eins.",
  "",
  "3.2 Beschreiben Sie die potenziellen Kunden",
  "Antwort zu zwei.",
  "",
  "3.3 Besondere Energierelevanz des Projekts",
  "[[Angabe ergänzen: Antwort fachlich ergänzen]]",
].join("\n")

function vcDraft(text: string = TEMPLATE_TEXT) {
  return {
    draft_id: "d-vc",
    field_id: VC,
    field_name: "Value Creation",
    status: "draft",
    current_version: {
      draft_version_id: "v1", text, character_count: text.length,
      created_by: "template", created_at: new Date().toISOString(), content_hash: "h",
    },
    character_count: text.length,
    character_limit: 15000,
    open_issue_count: 0,
    evidence_links: [],
    open_issues: [],
  }
}

function reviewPkg() {
  return {
    run_id: "r1", requirements: [], fields: [], findings: [], approval_status: "blocked",
    blocker_count: 0, warning_count: 0, open_issues: [], review_package_version: "rpv",
    current_approval_scope_hash: "h".repeat(64), recheck_required: false, stale_finding_count: 0,
  }
}

function mockEditor(text?: string) {
  server.use(
    http.get("/api/capabilities", () => HttpResponse.json({
      api_version: "1.1.0", polling_interval_seconds: 2,
      supported_source_types: ["txt"], features: {}, generation_mode: "fake_demo",
    })),
    http.get("/api/runs/r1/fields", () => HttpResponse.json([vcDraft(text)])),
    http.get("/api/runs/r1/evidence", () => HttpResponse.json([])),
    http.get("/api/runs/r1/requirements", () => HttpResponse.json([])),
    http.get("/api/runs/r1/review", () => HttpResponse.json(reviewPkg())),
    http.get("/api/runs/r1/fields/:fieldId/suggestion", () =>
      HttpResponse.json({ detail: "not found" }, { status: 404 })
    ),
    http.get("/api/runs/r1/portal-fields", () => HttpResponse.json([
      {
        field_id: VC, section: "VC", label: "Value Creation", character_limit: 15000,
        mandatory_status: "required", support_mode: "draft", field_kind: "composite",
        display_mode: "editor", draft_available: true,
        subsections: [
          { marker: "3.1", label: "3.1 Beschreiben Sie die Business-Ziele und das Geschäftsmodell" },
          { marker: "3.2", label: "3.2 Beschreiben Sie die potenziellen Kunden" },
          { marker: "3.3", label: "3.3 Besondere Energierelevanz des Projekts" },
        ],
      },
    ]))
  )
}

function subsectionNav() {
  return screen.getByRole("navigation", { name: "Unterabschnitte" })
}

describe("Fokusansicht je Unterabschnitt (B1–B4)", () => {
  it("zeigt nur den Antwortbereich; Portalfrage als nicht editierbare Karte", async () => {
    mockEditor()
    render(<LiveEditor runId="r1" />)
    const textarea = (await screen.findByLabelText(
      "Entwurf Value Creation"
    )) as HTMLTextAreaElement
    // Nur der Antwortbereich von 3.1 — keine Portalfrage, kein 22k-Block;
    // der Zeilenumbruch-Separator zum nächsten Marker bleibt ausserhalb.
    expect(textarea.value).toBe("Antwort zu eins.")
    const question = screen.getByTestId("subsection-question")
    expect(question).toHaveTextContent("Portalfrage – nicht editierbar")
    expect(question).toHaveTextContent(
      "3.1 Beschreiben Sie die Business-Ziele und das Geschäftsmodell"
    )
    expect(question.querySelector("[contenteditable]")).toBeNull()
    // Segmentzähler UND Gesamtlimit bleiben sichtbar (B2).
    expect(screen.getByTestId("subsection-count")).toHaveTextContent(/Abschnitt 3\.1/)
    expect(screen.getAllByText(/15\D*000|15000/).length).toBeGreaterThan(0)
  })

  it("Abschnittswechsel verliert keine ungespeicherte Änderung", async () => {
    mockEditor()
    render(<LiveEditor runId="r1" />)
    const textarea = (await screen.findByLabelText(
      "Entwurf Value Creation"
    )) as HTMLTextAreaElement
    // In 3.1 tippen (ungespeichert) …
    fireEvent.change(textarea, {
      target: { value: "Antwort zu eins. NEU ergänzt." },
    })
    // … zu 3.2 wechseln …
    fireEvent.click(within(subsectionNav()).getByRole("button", { name: /3\.2/ }))
    expect(
      (screen.getByLabelText("Entwurf Value Creation") as HTMLTextAreaElement).value
    ).toBe("Antwort zu zwei.")
    expect(screen.getByTestId("subsection-question")).toHaveTextContent(
      "3.2 Beschreiben Sie die potenziellen Kunden"
    )
    // … und zurück: die Eingabe ist unverändert da (Single-Buffer-Garantie).
    fireEvent.click(within(subsectionNav()).getByRole("button", { name: /3\.1/ }))
    expect(
      (screen.getByLabelText("Entwurf Value Creation") as HTMLTextAreaElement).value
    ).toBe("Antwort zu eins. NEU ergänzt.")
  })

  it("speichert den korrekt reassemblierten Volltext", async () => {
    mockEditor()
    let patchedText: string | null = null
    server.use(
      http.patch(`/api/runs/r1/fields/${VC}`, async ({ request }) => {
        const body = (await request.json()) as { text: string }
        patchedText = body.text
        return HttpResponse.json(vcDraft(body.text))
      })
    )
    render(<LiveEditor runId="r1" />)
    const textarea = (await screen.findByLabelText(
      "Entwurf Value Creation"
    )) as HTMLTextAreaElement
    fireEvent.change(textarea, { target: { value: "Neue Antwort eins." } })
    fireEvent.click(screen.getByRole("button", { name: "Speichern" }))
    await screen.findByText(/erneute Prüfung ist vor der Freigabe erforderlich/)
    expect(patchedText).toBe(
      [
        "3.1 Beschreiben Sie die Business-Ziele und das Geschäftsmodell",
        "Neue Antwort eins.",
        "",
        "3.2 Beschreiben Sie die potenziellen Kunden",
        "Antwort zu zwei.",
        "",
        "3.3 Besondere Energierelevanz des Projekts",
        "[[Angabe ergänzen: Antwort fachlich ergänzen]]",
      ].join("\n")
    )
  })

  it("verschiebt markierten Text als Notiz und entfernt ihn aus dem Antrag (B5)", async () => {
    mockEditor()
    const comments: string[] = []
    server.use(
      http.post("/api/runs/r1/human-decisions", async ({ request }) => {
        const body = (await request.json()) as { comment?: string }
        comments.push(body.comment ?? "")
        return HttpResponse.json(
          {
            target_type: "portal_field_draft", target_id: "d-vc",
            action: "request_changes", comment: body.comment ?? "",
            decision_id: "dec1", user_id: "u1", run_id: "r1",
            created_at: new Date().toISOString(),
          },
          { status: 201 }
        )
      })
    )
    render(<LiveEditor runId="r1" />)
    const textarea = (await screen.findByLabelText(
      "Entwurf Value Creation"
    )) as HTMLTextAreaElement
    // «Antwort zu eins.» markieren (0–16) und in die Notizen verschieben.
    textarea.focus()
    textarea.setSelectionRange(0, 16)
    fireEvent.click(screen.getByRole("button", { name: "In Notizen verschieben" }))
    await screen.findByText(/In die Notizen verschoben/)
    expect(comments).toEqual(["[Notiz] Antwort zu eins."])
    // Der Text hat den Antragsentwurf verlassen (dirty, nicht gespeichert).
    expect(
      (screen.getByLabelText("Entwurf Value Creation") as HTMLTextAreaElement).value
    ).toBe("")
  })

  it("verlangt eine Auswahl, bevor etwas verschoben wird (B5)", async () => {
    mockEditor()
    render(<LiveEditor runId="r1" />)
    await screen.findByLabelText("Entwurf Value Creation")
    fireEvent.click(screen.getByRole("button", { name: "In Notizen verschieben" }))
    expect(
      await screen.findByText(/Bitte zuerst den Text markieren/)
    ).toBeInTheDocument()
  })

  it("degradiert ehrlich zum Volltext-Editor, wenn Marker verändert wurden", async () => {
    mockEditor("Freitext ohne die erwarteten Abschnittsmarker.")
    render(<LiveEditor runId="r1" />)
    const textarea = (await screen.findByLabelText(
      "Entwurf Value Creation"
    )) as HTMLTextAreaElement
    expect(textarea.value).toBe("Freitext ohne die erwarteten Abschnittsmarker.")
    expect(
      screen.getByText(/Abschnittsmarker .* verändert/)
    ).toBeInTheDocument()
    expect(screen.queryByTestId("subsection-question")).toBeNull()
    // Gespeicherter Stand == lokaler Stand → nichts wiederherzustellen.
    expect(
      screen.queryByRole("button", { name: "Gespeicherten Stand wiederherstellen" })
    ).toBeNull()
  })

  it("bietet im Degraded-Banner die Wiederherstellung des gespeicherten Stands an", async () => {
    // Lokale (ungespeicherte) Änderung zerlegt die Struktur (dupliziertes 3.2)
    // → Banner + Rettungsanker; Klick stellt den gespeicherten Stand wieder
    // her und die Fokusansicht kehrt zurück.
    mockEditor()
    render(<LiveEditor runId="r1" />)
    const textarea = (await screen.findByLabelText(
      "Entwurf Value Creation"
    )) as HTMLTextAreaElement
    fireEvent.change(textarea, {
      target: { value: "Antwort zu eins.\n3.2 dupliziert" },
    })
    expect(
      await screen.findByText(/Abschnittsmarker .* verändert/)
    ).toBeInTheDocument()
    fireEvent.click(
      screen.getByRole("button", { name: "Gespeicherten Stand wiederherstellen" })
    )
    // Struktur intakt → Fokusansicht mit Portalfrage ist zurück.
    expect(await screen.findByTestId("subsection-question")).toBeInTheDocument()
    expect(screen.queryByText(/Abschnittsmarker .* verändert/)).toBeNull()
    const restored = (await screen.findByLabelText(
      "Entwurf Value Creation"
    )) as HTMLTextAreaElement
    expect(restored.value).toBe("Antwort zu eins.")
  })
})
