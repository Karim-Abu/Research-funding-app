import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import { SuggestionReviewDialog } from "@/components/editor/suggestion-review-dialog"
import type { A2Suggestion } from "@/lib/redraft"

function suggestion(overrides: Partial<A2Suggestion> = {}): A2Suggestion {
  return {
    suggestion_id: "s1",
    operation_id: "op1",
    field_id: "SOL.INNOVATION_SOLUTION.EDITOR",
    base_version_id: "v1",
    suggested_text: "4.1 ... 4.2 ... 4.3 ... 4.4 ... 4.5 verbessert.",
    rationale: "An Belege angepasst.",
    evidence: [
      {
        anchor_id: "a1",
        quote: "Belegte Passage.",
        source_name: "Quelle.txt",
        verification_status: "exact_verified",
      },
    ],
    open_issue_ids: ["issue-1"],
    placeholders: [{ label: "Marktzahl", reason: "fehlt" }],
    character_count: 46,
    character_limit: 25000,
    warnings: ["contains_placeholders", "based_on_unconfirmed_facts"],
    research_sources: [],
    ...overrides,
  }
}

describe("SuggestionReviewDialog", () => {
  it("renders side-by-side, evidence, char count and warnings", () => {
    render(
      <SuggestionReviewDialog
        open
        onOpenChange={() => {}}
        currentText="Aktueller Entwurf."
        suggestion={suggestion()}
        onAccept={() => {}}
        onDismiss={() => {}}
      />
    )
    expect(screen.getByTestId("current-text").textContent).toContain("Aktueller Entwurf.")
    expect(screen.getByTestId("suggestion-text").textContent).toContain("4.5 verbessert.")
    expect(screen.getByTestId("character-count").textContent).toContain("46 / 25000")
    expect(screen.getByText("Quelle.txt")).toBeInTheDocument()
    expect(screen.getByText("Belegte Passage.")).toBeInTheDocument()
    expect(screen.getByTestId("warning-contains_placeholders")).toBeInTheDocument()
    expect(screen.getByTestId("warning-based_on_unconfirmed_facts")).toBeInTheDocument()
    expect(screen.getByTestId("open-issues").textContent).toContain("1")
  })

  it("calls onAccept; Ablehnen verlangt eine ausdrückliche Bestätigung", () => {
    const onAccept = vi.fn()
    const onDismiss = vi.fn()
    render(
      <SuggestionReviewDialog
        open
        onOpenChange={() => {}}
        currentText="x"
        suggestion={suggestion()}
        onAccept={onAccept}
        onDismiss={onDismiss}
      />
    )
    fireEvent.click(screen.getByRole("button", { name: "Übernehmen" }))
    expect(onAccept).toHaveBeenCalledOnce()
    // Ablehnen öffnet das Begründungs-Formular — erst Bestätigen ruft onDismiss.
    fireEvent.click(screen.getByRole("button", { name: "Vorschlag ablehnen" }))
    expect(onDismiss).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole("button", { name: "Fachlich unzutreffend" }))
    fireEvent.change(screen.getByLabelText("Eigener Ablehnungsgrund"), {
      target: { value: "Kernzahl stimmt nicht." },
    })
    fireEvent.click(screen.getByRole("button", { name: "Ablehnen bestätigen" }))
    expect(onDismiss).toHaveBeenCalledOnce()
    expect(onDismiss).toHaveBeenCalledWith(
      "Fachlich unzutreffend — Kernzahl stimmt nicht."
    )
  })

  it("RUN 4B §3/§10: sr-Diff-Zusammenfassung mit aria-live vorhanden", () => {
    render(
      <SuggestionReviewDialog
        open
        onOpenChange={() => {}}
        currentText={"Satz eins bleibt. Satz zwei fliegt raus."}
        suggestion={suggestion({
          suggested_text: "Satz eins bleibt. Ganz neuer Schlusssatz.",
        })}
        onAccept={() => {}}
        onDismiss={() => {}}
      />
    )
    const summary = screen.getByTestId("diff-sr-summary")
    expect(summary).toHaveAttribute("aria-live", "polite")
    expect(summary).toHaveTextContent(/1 Satz ergänzt, 1 Satz entfernt/)
  })

  it("zeigt echten Diff mit Text-Badges und übernimmt einzelne Änderungen", () => {
    const onAcceptPartial = vi.fn()
    render(
      <SuggestionReviewDialog
        open
        onOpenChange={() => {}}
        currentText={"4.2 Neuheit\nSatz eins bleibt. Satz zwei fliegt raus."}
        suggestion={suggestion({
          suggested_text:
            "4.2 Neuheit\nSatz eins bleibt. Ganz neuer Schlusssatz.",
        })}
        onAccept={() => {}}
        onAcceptPartial={onAcceptPartial}
        onDismiss={() => {}}
      />
    )
    // Klassifikation als Text-Badge, nicht nur Farbe (a11y).
    expect(screen.getByText("Entfernt")).toBeInTheDocument()
    expect(screen.getByText("Neu")).toBeInTheDocument()
    // Nur den neuen Schlusssatz übernehmen (Checkbox + Aktion).
    fireEvent.click(
      screen.getByLabelText("Änderung übernehmen: Ganz neuer Schlusssatz.")
    )
    fireEvent.click(
      screen.getByRole("button", { name: "Ausgewählte übernehmen (1)" })
    )
    expect(onAcceptPartial).toHaveBeenCalledOnce()
    const merged = onAcceptPartial.mock.calls[0][0] as string
    expect(merged).toContain("Ganz neuer Schlusssatz.")
    expect(merged).toContain("Satz zwei fliegt raus.") // nicht gewählt ⇒ bleibt
    expect(merged.startsWith("4.2 Neuheit\n")).toBe(true)
  })

  it("blendet partielle Übernahme für manifestgebundene Vorschläge aus", () => {
    render(
      <SuggestionReviewDialog
        open
        onOpenChange={() => {}}
        currentText="Alter Satz."
        suggestion={suggestion({
          suggested_text: "Neuer Satz.",
          manifest_id: "manifest-1",
          accept_mode: "whole_suggestion_only",
        })}
        onAccept={() => {}}
        onAcceptPartial={() => {}}
        onDismiss={() => {}}
      />
    )
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument()
    expect(
      screen.queryByRole("button", { name: /Ausgewählte übernehmen/ })
    ).not.toBeInTheDocument()
    expect(screen.getByTestId("suggestion-manifest-summary")).toBeInTheDocument()
  })

  it("verhindert die Übernahme eines veralteten Manifest-Vorschlags", () => {
    render(
      <SuggestionReviewDialog
        open
        onOpenChange={() => {}}
        currentText="Alter Satz."
        suggestion={suggestion({
          suggested_text: "Neuer Satz.",
          manifest_id: "manifest-1",
          accept_mode: "whole_suggestion_only",
          stale_reason: "source_version_changed",
        })}
        onAccept={() => {}}
        onDismiss={() => {}}
      />
    )
    expect(screen.getByRole("button", { name: "Übernehmen" })).toBeDisabled()
    // RUN 4B §4 — Klartext-Grund statt Roh-Code, plus nächste Aktion.
    expect(screen.getByTestId("suggestion-stale-notice")).toHaveTextContent(
      "Vorschlag veraltet: Eine verwendete Quelle liegt in neuer Version vor. Erzeugen Sie einen neuen Vorschlag."
    )
    expect(screen.queryByText(/source_version_changed/)).toBeNull()
  })

  it("RUN 4B §5/§6: Fehlende-Angaben-Sektion ohne Requirement-IDs + Beleg-Hauptzeile", () => {
    render(
      <SuggestionReviewDialog
        open
        onOpenChange={() => {}}
        currentText="x"
        suggestion={suggestion({
          target_section: "4.5",
          missing_inputs: [
            {
              label: "Schweizer Marktgrösse",
              reason: "Ohne belegte Zahl bleibt der Abschnitt unvollständig.",
              key: "swiss_market",
              requirement_ids: ["REQ.VC.MARKET.SIZE"],
            },
          ],
        })}
        onAccept={() => {}}
        onDismiss={() => {}}
      />
    )
    const missing = screen.getByTestId("missing-inputs-section")
    expect(missing).toHaveTextContent("Fehlende Angaben (1)")
    expect(missing).toHaveTextContent("Schweizer Marktgrösse")
    expect(missing).toHaveTextContent(
      "Warum wichtig: Ohne belegte Zahl bleibt der Abschnitt unvollständig."
    )
    expect(missing).toHaveTextContent("Innolink-Punkt 4.5")
    expect(missing).toHaveTextContent("bleiben nach einer Übernahme als offene Aufgaben sichtbar")
    // Keine technischen Requirement-IDs im Hauptfluss.
    expect(missing).not.toHaveTextContent("REQ.VC.MARKET.SIZE")
    // Beleg-Hauptzeile in Nutzersprache; Details aufklappbar.
    expect(screen.getByTestId("evidence-usage")).toHaveTextContent(
      "Dieser Vorschlag verwendet 1 geprüften Beleg."
    )
    expect(screen.getByText("Belegdetails anzeigen")).toBeInTheDocument()
  })

  it("RUN 4B §6: Read-Pfad ohne Belegdetails bleibt ehrlich (Zahl aus Proposal)", () => {
    render(
      <SuggestionReviewDialog
        open
        onOpenChange={() => {}}
        currentText="x"
        suggestion={suggestion({
          evidence: [],
          proposal: {
            suggestion_text: "4.5 verbessert.",
            used_anchor_ids: ["a1", "a2"],
            used_research_source_ids: [],
            missing_inputs: [],
            profile_id: "A2.solution",
            prompt_version: null,
            context_hash: null,
            created_at: new Date().toISOString(),
            data_mode: "offline",
            human_review_required: true,
          },
        })}
        onAccept={() => {}}
        onDismiss={() => {}}
      />
    )
    const usage = screen.getByTestId("evidence-usage")
    expect(usage).toHaveTextContent("Dieser Vorschlag verwendet 2 geprüfte Belege.")
    expect(usage).toHaveTextContent(
      "Die Fundstellen-Details stehen für gespeicherte Vorschläge nicht zur Verfügung"
    )
    expect(screen.queryByText("Belegdetails anzeigen")).toBeNull()
  })

  it("RUN 4B §4: fake_demo-Warnung erscheint als Klartext, nie als Roh-Code", () => {
    render(
      <SuggestionReviewDialog
        open
        onOpenChange={() => {}}
        currentText="x"
        suggestion={suggestion({ warnings: ["fake_demo_no_model"] })}
        onAccept={() => {}}
        onDismiss={() => {}}
      />
    )
    expect(screen.getByTestId("warning-fake_demo_no_model")).toHaveTextContent(
      "Demo-Vorschlag ohne echtes KI-Modell"
    )
    expect(screen.queryByText("fake_demo_no_model")).toBeNull()
  })

  it("RUN 4B §7: «Neuen Vorschlag erzeugen» ruft onRegenerate ohne Ablehnung", () => {
    const onRegenerate = vi.fn()
    const onDismiss = vi.fn()
    render(
      <SuggestionReviewDialog
        open
        onOpenChange={() => {}}
        currentText="x"
        suggestion={suggestion({ stale_reason: "draft_version_changed" })}
        onAccept={() => {}}
        onDismiss={onDismiss}
        onRegenerate={onRegenerate}
      />
    )
    // Beim veralteten Vorschlag ist Regenerate die empfohlene Aktion —
    // Übernehmen bleibt deaktiviert.
    expect(screen.getByRole("button", { name: "Übernehmen" })).toBeDisabled()
    fireEvent.click(screen.getByTestId("regenerate-suggestion"))
    expect(onRegenerate).toHaveBeenCalledOnce()
    expect(onDismiss).not.toHaveBeenCalled()
  })

  it("«Eigene Bearbeitung öffnen» ruft onEdit ohne Ablehnung", () => {
    const onEdit = vi.fn()
    const onDismiss = vi.fn()
    render(
      <SuggestionReviewDialog
        open
        onOpenChange={() => {}}
        currentText="x"
        suggestion={suggestion()}
        onAccept={() => {}}
        onEdit={onEdit}
        onDismiss={onDismiss}
      />
    )
    fireEvent.click(screen.getByRole("button", { name: "Eigene Bearbeitung öffnen" }))
    expect(onEdit).toHaveBeenCalledOnce()
    expect(onDismiss).not.toHaveBeenCalled()
  })

  it("zeigt konkrete Begründungs-Chips aus dem section_result (C5)", () => {
    render(
      <SuggestionReviewDialog
        open
        onOpenChange={() => {}}
        currentText="x"
        suggestion={suggestion({
          section_result: {
            field_id: "SOL.INNOVATION_SOLUTION.EDITOR",
            target_section: "4.2",
            suggested_text: "…",
            rationale: "ok",
            preserved_facts: [],
            removed_or_reframed_claims: ["Wiederholte Marktbehauptung"],
            new_claims: ["Neue Effizienzaussage"],
            missing_inputs: [{ label: "KPI-Baseline", reason: "fehlt" }],
            evidence_anchor_ids: [],
            open_issue_ids: [],
          },
        })}
        onAccept={() => {}}
        onDismiss={() => {}}
      />
    )
    const chips = screen.getByTestId("rationale-chips")
    expect(chips).toHaveTextContent("Entfernt/Umformuliert: Wiederholte Marktbehauptung")
    expect(chips).toHaveTextContent("Neue Aussage (ungeprüft): Neue Effizienzaussage")
    expect(chips).toHaveTextContent("Offen gelassen: KPI-Baseline — fehlt")
  })

  // Anf. 3 — fachliche Kurzbilanz VOR dem Diff, gezählt aus dem section_result.
  it("Zusammenfassung vor dem Diff zählt SectionResult-Daten korrekt", () => {
    render(
      <SuggestionReviewDialog
        open
        onOpenChange={() => {}}
        currentText="Alter Text."
        suggestion={suggestion({
          suggested_text: "Neuer, längerer Text.",
          research_sources: [{
            source_id: "research-1",
            title: "Swiss market report",
            url: "https://research.example.edu/report",
            research_module: "market_growth",
            support_status: "supports",
            content_review_status: "reviewed",
          }],
          section_result: {
            field_id: "SOL.INNOVATION_SOLUTION.EDITOR",
            target_section: "4.2",
            suggested_text: "Neuer, längerer Text.",
            rationale: "ok",
            preserved_facts: ["Projektbegriff", "Konsortium"],
            removed_or_reframed_claims: ["Wiederholte Marktbehauptung"],
            new_claims: [],
            missing_inputs: [{ label: "KPI-Baseline", reason: "fehlt" }],
            evidence_anchor_ids: ["a1"],
            open_issue_ids: [],
          },
        })}
        onAccept={() => {}}
        onDismiss={() => {}}
      />
    )
    const summary = screen.getByTestId("suggestion-summary")
    expect(summary).toHaveTextContent("Erhaltene Fakten: 2")
    expect(summary).toHaveTextContent("Entfernte/umformulierte Aussagen: 1")
    expect(summary).toHaveTextContent("Neu eingeführte Aussagen: 0")
    expect(summary).toHaveTextContent("Fehlende Angaben: 1")
    expect(summary).toHaveTextContent("Verwendete Belege: 1")
    expect(summary).toHaveTextContent("Research-Quellen: 1")
    expect(summary).toHaveTextContent(
      `Zeichen: ${"Alter Text.".length} → ${"Neuer, längerer Text.".length}`
    )
    // Keine Provider-/Modellangaben im normalen Bereich.
    expect(summary.textContent).not.toMatch(/anthropic|openai|gpt|claude|modell/i)
  })

  it("ohne section_result keine Zusammenfassung", () => {
    render(
      <SuggestionReviewDialog
        open
        onOpenChange={() => {}}
        currentText="x"
        suggestion={suggestion()}
        onAccept={() => {}}
        onDismiss={() => {}}
      />
    )
    expect(screen.queryByTestId("suggestion-summary")).toBeNull()
  })

  it("disables accept when over the character limit", () => {
    const onAccept = vi.fn()
    render(
      <SuggestionReviewDialog
        open
        onOpenChange={() => {}}
        currentText="x"
        suggestion={suggestion({ character_count: 26000 })}
        onAccept={onAccept}
        onDismiss={() => {}}
      />
    )
    const accept = screen.getByRole("button", { name: "Übernehmen" })
    expect(accept).toBeDisabled()
  })

  it("shows actually used research sources separately from evidence", () => {
    render(
      <SuggestionReviewDialog
        open
        onOpenChange={() => {}}
        currentText="x"
        suggestion={suggestion({
          research_sources: [{
            source_id: "research-1",
            title: "Swiss market report",
            url: "https://research.example.edu/report",
            research_module: "market_growth",
            support_status: "supports",
            content_review_status: "reviewed",
          }],
        })}
        onAccept={() => {}}
        onDismiss={() => {}}
      />
    )
    expect(screen.getByText("Verwendete Research-Quellen")).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "Swiss market report" })).toHaveAttribute(
      "href", "https://research.example.edu/report",
    )
    expect(screen.getByText(
      "Vom Nutzer geprüfte öffentliche Quelle – keine automatische fachliche Freigabe"
    )).toBeInTheDocument()
  })
})
