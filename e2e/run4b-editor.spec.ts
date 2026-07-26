// RUN 4B — Browser-E2E des Schreibassistenten (E2E-EDITOR-01..04, MARKET-01).
//
// Methodik (Mandat §11, keine Live-Providercalls):
// - EDITOR-02/-03 laufen REAL gegen den lokalen Fake-Provider-Backend
//   (AGENT_FAKE_PROVIDER=true): Accept-/Replay-Idempotenz und serverseitige
//   Staleness sind dort deterministisch.
// - EDITOR-01/-04 und MARKET-01 nutzen deterministische page.route()-Fixtures
//   NUR dort, wo der Fake-Backend den Zustand offline nicht herstellen kann
//   (strukturierte missing_inputs/Belege, Provider-503, Markt-Zustände).
//   Fixtures tragen IMMER generation_kind "fake_demo" + fake_demo-Warnung —
//   nie ein fingiertes model_generated.
import { test, expect, type APIRequestContext, type Page } from "@playwright/test"

const EMAIL = process.env.E2E_EMAIL ?? "anna.keller@example.test"
const PASSWORD = process.env.E2E_PASSWORD ?? "changeme-dev-lead"
const ORIGIN = "http://localhost:3000"
const SOL = "SOL.INNOVATION_SOLUTION.EDITOR"
const VC = "VC.BUSINESS_TARGETS_MODEL.EDITOR"
const CLASSIFICATION = {
  sensitivity: "public",
  origin: "synthetic",
  processing_mode: "deterministic_only",
  web_research_mode: "off",
  nda_applies: false,
}

function idem(): string {
  return Math.random().toString(36).slice(2) + Date.now().toString(36)
}

async function waitOp(
  request: APIRequestContext,
  operationId: string
): Promise<string> {
  let status = ""
  for (let i = 0; i < 60; i++) {
    status = (await (await request.get(`/api/operations/${operationId}`)).json())
      .status
    if (["succeeded", "failed", "cancelled"].includes(status)) break
    await new Promise((r) => setTimeout(r, 500))
  }
  return status
}

async function login(page: Page) {
  await page.goto("/login")
  await page.getByLabel("E-Mail").fill(EMAIL)
  await page.getByLabel("Passwort").fill(PASSWORD)
  await page.getByRole("button", { name: "Anmelden" }).click()
  await expect(page).toHaveURL(/\/$/, { timeout: 20_000 })
  const csrf = (await (await page.request.get("/api/session")).json())
    .csrf_token as string
  return () => ({
    "X-CSRF-Token": csrf,
    Origin: ORIGIN,
    "Idempotency-Key": idem(),
    "Content-Type": "application/json",
  })
}

/** Cloud-Projekt + Lauf (Fake-Provider) — Muster aus a2-solution-innovation. */
async function setupCloudRun(page: Page, mut: () => Record<string, string>, title: string) {
  const projectId = (
    await (
      await page.request.post("/api/projects", {
        headers: mut(),
        data: {
          title,
          description: "RUN 4B Editor-E2E.",
          funding_instrument_profile_id:
            "innosuisse_innovation_project_with_implementation_partner",
          data_classification: CLASSIFICATION,
        },
      })
    ).json()
  ).project_id as string

  await page.request.post(`/api/projects/${projectId}/sources/text`, {
    headers: mut(),
    data: {
      name: "Notiz",
      text: "Synthetic public project content for the RUN 4B editor flow.",
      data_classification: CLASSIFICATION,
    },
  })
  let sourceVersionId = ""
  for (let i = 0; i < 40; i++) {
    const list = (await (
      await page.request.get(`/api/projects/${projectId}/sources`)
    ).json()) as { status: string; current_source_version_id?: string }[]
    const ready = list.find(
      (s) => s.status === "processed" && s.current_source_version_id
    )
    if (ready?.current_source_version_id) {
      sourceVersionId = ready.current_source_version_id
      break
    }
    await page.waitForTimeout(500)
  }
  expect(sourceVersionId).not.toBe("")

  const confirmation = await page.request.post(
    `/api/projects/${projectId}/processing-confirmations`,
    {
      headers: mut(),
      data: {
        processing_mode: "cloud_assisted",
        source_version_ids: [sourceVersionId],
        accepted_policy_version: "1.1.0",
        purpose: "KI-Vorschläge für Textentwürfe vorbereiten",
        expires_after_one_run: true,
      },
    }
  )
  expect(confirmation.status()).toBe(201)
  const confirmationId = (await confirmation.json()).confirmation_id as string

  const accepted = await (
    await page.request.post(`/api/projects/${projectId}/runs`, {
      headers: mut(),
      data: {
        settings: {
          processing_mode: "cloud_assisted",
          max_cost_chf: 5,
          max_llm_calls: 25,
          max_web_calls: 0,
          source_version_ids: [sourceVersionId],
          internal_cloud_confirmation_id: confirmationId,
        },
      },
    })
  ).json()
  expect(await waitOp(page.request, accepted.operation_id)).toBe("succeeded")
  const runId = accepted.resource_id as string

  // Aktives Projekt im Browser setzen (Editor liest die Session-Auswahl).
  await page.goto("/")
  await page.getByRole("heading", { name: title }).click()
  await expect(page).not.toHaveURL(/\/$/, { timeout: 20_000 })
  return { projectId, runId }
}

async function versionCount(
  request: APIRequestContext,
  runId: string,
  fieldId: string
): Promise<number> {
  const body = await (
    await request.get(`/api/runs/${runId}/fields/${fieldId}/versions`)
  ).json()
  return (body.versions as unknown[]).length
}

test.describe.serial("RUN 4B — Schreibassistent", () => {
  test("E2E-EDITOR-02: Generate → Accept → genau eine Version → Replay → Restore", async ({
    page,
  }) => {
    test.setTimeout(300_000)
    const mut = await login(page)
    const { runId } = await setupCloudRun(page, mut, `RUN4B Editor A ${idem()}`)

    const draft = await (
      await page.request.get(`/api/runs/${runId}/fields/${SOL}`)
    ).json()
    const base = draft.current_version.draft_version_id as string
    const versionsBefore = await versionCount(page.request, runId, SOL)

    // Vorschlag erzeugen (Fake-Provider, deterministisch) über den API-Pfad.
    const redraft = await page.request.post(
      `/api/runs/${runId}/fields/${SOL}/redrafts`,
      {
        headers: mut(),
        data: {
          base_version_id: base,
          target_section: "4.1",
          improvement_mode: "clearer",
        },
      }
    )
    expect(redraft.status()).toBe(202)
    const redraftOp = (await redraft.json()).operation_id as string
    expect(await waitOp(page.request, redraftOp)).toBe("succeeded")
    const suggestion = (
      await (await page.request.get(`/api/operations/${redraftOp}`)).json()
    ).result

    // UI: Vorschlag prüfen (Read-Pfad) → Original/Vorschlag sichtbar.
    await page.goto(`/editor?field=${SOL}`)
    await page.getByRole("button", { name: "Vorschläge", exact: true }).click()
    await page.getByRole("button", { name: "Vorschlag prüfen" }).click()
    await expect(page.getByTestId("current-text")).toBeVisible({
      timeout: 20_000,
    })
    await expect(page.getByTestId("suggestion-text")).toBeVisible()
    await page.keyboard.press("Escape")

    // Vollständige Übernahme über den serverseitigen Accept-Pfad mit festem
    // Idempotency-Key (Replay = identischer Key, identische Payload).
    const acceptKey = idem()
    const acceptHeaders = () => ({ ...mut(), "Idempotency-Key": acceptKey })
    const acceptUrl = `/api/runs/${runId}/fields/${SOL}/suggestions/${suggestion.suggestion_id}/accept`
    const first = await page.request.post(acceptUrl, {
      headers: acceptHeaders(),
      data: { base_version_id: suggestion.base_version_id },
    })
    expect(first.status()).toBe(200)
    expect((await first.json()).idempotent_replay).toBe(false)
    expect(await versionCount(page.request, runId, SOL)).toBe(
      versionsBefore + 1
    )

    // Replay: gleicher Key, gleiche Payload → keine zweite Version.
    const replay = await page.request.post(acceptUrl, {
      headers: acceptHeaders(),
      data: { base_version_id: suggestion.base_version_id },
    })
    expect(replay.status()).toBe(200)
    expect((await replay.json()).idempotent_replay).toBe(true)
    expect(await versionCount(page.request, runId, SOL)).toBe(
      versionsBefore + 1
    )

    // UI zeigt die neue Version mit Herkunft «Aus KI-Vorschlag übernommen»;
    // die Originalversion bleibt über die Historie erreichbar.
    await page.goto(`/editor?field=${SOL}`)
    await expect(
      page.getByText("Aus KI-Vorschlag übernommen").first()
    ).toBeVisible({ timeout: 20_000 })

    // Restore-Smoke: Vorgängerversion über den Versionen-Tab wiederherstellen.
    await page.goto(`/editor?field=${SOL}`)
    await page.getByRole("button", { name: "Prüfen", exact: true }).click()
    await page.getByRole("tab", { name: "Versionen" }).click()
    const restoreButtons = page.getByRole("button", { name: "Wiederherstellen" })
    await expect(restoreButtons.first()).toBeVisible({ timeout: 20_000 })
    await restoreButtons.first().click()
    await expect(
      page.getByText(
        "Frühere Version wiederhergestellt und als neue Version gespeichert."
      )
    ).toBeVisible({ timeout: 20_000 })
    expect(await versionCount(page.request, runId, SOL)).toBe(
      versionsBefore + 2
    )
  })

  test("E2E-EDITOR-03: stale Suggestion → Übernahme blockiert + nächste Aktion", async ({
    page,
  }) => {
    test.setTimeout(300_000)
    const mut = await login(page)
    const { runId } = await setupCloudRun(page, mut, `RUN4B Editor B ${idem()}`)

    const draft = await (
      await page.request.get(`/api/runs/${runId}/fields/${VC}`)
    ).json()
    const base = draft.current_version.draft_version_id as string

    const redraft = await page.request.post(
      `/api/runs/${runId}/fields/${VC}/redrafts`,
      {
        headers: mut(),
        data: {
          base_version_id: base,
          target_section: "3.1",
          improvement_mode: "clearer",
        },
      }
    )
    expect(redraft.status()).toBe(202)
    expect(await waitOp(page.request, (await redraft.json()).operation_id)).toBe(
      "succeeded"
    )

    // Feld ändern → der gespeicherte Vorschlag ist serverseitig veraltet.
    const patch = await page.request.patch(`/api/runs/${runId}/fields/${VC}`, {
      headers: mut(),
      data: {
        base_version_id: base,
        text: "3.1 Geschäftsmodell\nNeuer Stand nach dem Vorschlag.\n3.2 Kundensegmente\nOffen.\n3.3 Marktgrösse\nOffen.",
      },
    })
    expect(patch.status()).toBe(200)

    // (a) REAL: nach der Feldänderung bietet der Server den basisfremden
    // Vorschlag GAR NICHT mehr an (fail-closed, draft_version_changed) —
    // es gibt nichts Veraltetes zu übernehmen.
    await page.goto(`/editor?field=${VC}`)
    await page.getByRole("button", { name: "Vorschläge", exact: true }).click()
    await expect(page.getByTestId("a2-suggestion-control")).toBeVisible({
      timeout: 20_000,
    })
    await expect(
      page.getByRole("button", { name: "Vorschlag prüfen" })
    ).toHaveCount(0)

    // (b) FIXTURE: liefert der Server einen manifest-stale Vorschlag (z. B.
    // Quelle in neuer Version), blockiert die UI die Übernahme mit Klartext
    // und benannter nächster Aktion. Ehrlich als fake_demo gekennzeichnet.
    const current = await (
      await page.request.get(`/api/runs/${runId}/fields/${VC}`)
    ).json()
    await page.route(`**/api/runs/${runId}/fields/${VC}/suggestion*`, (route) =>
      route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          suggestion: {
            suggestion_id: "fx-stale-1",
            operation_id: "fx-stale-op",
            field_id: VC,
            target_section: "3.1",
            generation_kind: "fake_demo",
            execution_mode: "fake_demo",
            base_version_id: current.current_version.draft_version_id,
            suggested_text: "3.1 Geschäftsmodell\nVeralteter Vorschlagstext.",
            rationale: "An verfügbare Belege angepasst.",
            evidence: [],
            research_sources: [],
            open_issue_ids: [],
            placeholders: [],
            character_count: 44,
            character_limit: 15000,
            warnings: ["fake_demo_no_model"],
            missing_inputs: [],
            manifest_id: "fx-stale-manifest",
            accept_mode: "whole_suggestion_only",
            stale_reason: "source_version_changed",
            improvement_mode: "clearer",
          },
        }),
      })
    )
    await page.goto(`/editor?field=${VC}`)
    await page.getByRole("button", { name: "Vorschläge", exact: true }).click()
    await page.getByRole("button", { name: "Vorschlag prüfen" }).click()
    await expect(page.getByTestId("suggestion-stale-notice")).toBeVisible({
      timeout: 20_000,
    })
    await expect(page.getByTestId("suggestion-stale-notice")).toContainText(
      "Vorschlag veraltet: Eine verwendete Quelle liegt in neuer Version vor."
    )
    // Übernahme blockiert; die nächste Aktion ist benannt und klickbar.
    await expect(
      page.getByRole("button", { name: "Übernehmen", exact: true })
    ).toBeDisabled()
    await expect(page.getByTestId("regenerate-suggestion")).toBeEnabled()
  })

  test("E2E-EDITOR-01: Vorschlag mit Fehlenden Angaben und Belegen (Fixture)", async ({
    page,
  }) => {
    test.setTimeout(240_000)
    const mut = await login(page)
    const { runId } = await setupCloudRun(page, mut, `RUN4B Editor C ${idem()}`)
    const draft = await (
      await page.request.get(`/api/runs/${runId}/fields/${SOL}`)
    ).json()

    // Deterministische Fixture NUR für den Suggestion-Read — ehrlich als
    // fake_demo gekennzeichnet (nie fingiertes model_generated).
    await page.route(`**/api/runs/${runId}/fields/${SOL}/suggestion*`, (route) =>
      route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          suggestion: {
            suggestion_id: "fixture-s1",
            operation_id: "fixture-op1",
            field_id: SOL,
            target_section: "4.2",
            generation_kind: "fake_demo",
            execution_mode: "fake_demo",
            base_version_id: draft.current_version.draft_version_id,
            suggested_text:
              "4.1 Ausgangslage bleibt.\n4.2 Neuheit: klarere Darstellung mit zwei Belegen.",
            rationale: "An verfügbare Belege und Anforderungen angepasst.",
            evidence: [
              {
                anchor_id: "fx-a1",
                quote: "Belegte Passage eins.",
                source_name: "Quelle-1.txt",
                verification_status: "exact_verified",
                page: 2,
              },
              {
                anchor_id: "fx-a2",
                quote: "Belegte Passage zwei.",
                source_name: "Quelle-2.txt",
                verification_status: "exact_verified",
                section: "2.1",
              },
            ],
            research_sources: [],
            open_issue_ids: [],
            placeholders: [],
            character_count: 84,
            character_limit: 25000,
            warnings: ["fake_demo_no_model"],
            missing_inputs: [
              {
                key: "swiss_market_size",
                label: "Schweizer Marktgrösse",
                reason: "Ohne belegte Zahl bleibt der Abschnitt unvollständig.",
                requirement_ids: ["REQ.VC.MARKET.SIZE"],
              },
              {
                key: "trl_evidence",
                label: "TRL-Nachweis",
                reason: "Der Reifegrad braucht eine nachvollziehbare Quelle.",
                requirement_ids: [],
              },
            ],
            manifest_id: "fixture-manifest",
            accept_mode: "whole_suggestion_only",
            improvement_mode: "complete_innolink_requirements",
          },
        }),
      })
    )

    await page.goto(`/editor?field=${SOL}`)
    await page.getByRole("button", { name: "Vorschläge", exact: true }).click()
    // Modus-Auswahl trägt die Mandats-Copy.
    await expect(
      page.locator('option[value="complete_innolink_requirements"]')
    ).toHaveText("Fehlende Innolink-Punkte ergänzen")

    await page.getByRole("button", { name: "Vorschlag prüfen" }).click()
    await expect(page.getByTestId("current-text")).toBeVisible({
      timeout: 20_000,
    })
    await expect(page.getByTestId("suggestion-text")).toBeVisible()
    // Ehrliche Demo-Kennzeichnung.
    await expect(
      page.getByTestId("suggestion-review-sheet").getByText("Demo", { exact: true })
    ).toBeVisible()
    // §5 Fehlende Angaben — ohne Requirement-IDs.
    const missing = page.getByTestId("missing-inputs-section")
    await expect(missing).toContainText("Fehlende Angaben (2)")
    await expect(missing).toContainText("Schweizer Marktgrösse")
    await expect(missing).not.toContainText("REQ.VC.MARKET.SIZE")
    // §6 Belege-Hauptzeile + aufklappbare Details.
    await expect(page.getByTestId("evidence-usage")).toContainText(
      "Dieser Vorschlag verwendet 2 geprüfte Belege."
    )
    await page.getByText("Belegdetails anzeigen").click()
    await expect(page.getByText("Quelle-1.txt · S. 2")).toBeVisible()
  })

  test("E2E-EDITOR-04: Provider nicht verfügbar → ehrlicher Fehler, kein Demo-Fallback", async ({
    page,
  }) => {
    test.setTimeout(240_000)
    const mut = await login(page)
    const { runId } = await setupCloudRun(page, mut, `RUN4B Editor D ${idem()}`)

    await page.route(`**/api/runs/${runId}/fields/${SOL}/suggestion*`, (route) =>
      route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({ suggestion: null }),
      })
    )
    await page.route(`**/api/runs/${runId}/fields/${SOL}/redrafts`, (route) =>
      route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({
          code: "ai_unavailable",
          reason_code: "provider_unavailable",
        }),
      })
    )

    await page.goto(`/editor?field=${SOL}`)
    await page.getByRole("button", { name: "Vorschläge", exact: true }).click()
    await page
      .getByTestId("a2-suggestion-control")
      .getByRole("button", { name: /Vorschlag erstellen|Demo-Vorschlag erstellen|Text mit KI verbessern/ })
      .first()
      .click()

    // Ehrlicher Blockgrund mit CTA — und NIRGENDS ein Demo-Ersatzvorschlag.
    await expect(
      page.getByText(/kein freigegebener KI-Provider konfiguriert/)
    ).toBeVisible({ timeout: 20_000 })
    await expect(page.getByTestId("a2-suggestion-summary")).toHaveCount(0)
    await expect(page.getByTestId("suggestion-review-sheet")).toHaveCount(0)
  })

  test("E2E-MARKET-01: Editor liest zentrales Artefakt — limited ehrlich, max. 3 Findings", async ({
    page,
  }) => {
    test.setTimeout(240_000)
    const mut = await login(page)
    const { projectId, runId } = await setupCloudRun(
      page,
      mut,
      `RUN4B Editor E ${idem()}`
    )

    // (a) limited ohne Items → ehrliche Copy, kein leerer Erfolg.
    await page.route(
      `**/api/projects/${projectId}/market-comparisons/latest`,
      (route) =>
        route.fulfill({
          contentType: "application/json",
          body: JSON.stringify({
            comparison_id: "fx-c1",
            project_id: projectId,
            status: "limited",
            comparison_version: 1,
            research_gaps: ["Es fehlen geprüfte Quellen zu Anbietern."],
            warnings: [],
            item_count: 0,
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
            items: [],
          }),
        })
    )
    await page.goto(`/editor?field=${VC}`)
    await page.getByRole("button", { name: "Prüfen", exact: true }).click()
    await page.getByRole("tab", { name: "Markt & Wettbewerb" }).click()
    await expect(page.getByTestId("market-editor-empty")).toContainText(
      "Marktinformationen vorhanden, aber noch kein belastbarer Anbieter-/Alternativenvergleich."
    )
    await expect(
      page.getByRole("button", { name: "Details öffnen" })
    ).toBeDisabled()

    // (b) belegte Einträge → Rail zeigt nur Kennzahlen, Sheet öffnet die
    // zentrale Tabelle; im Editor existiert kein «Vergleich erstellen».
    await page.unroute(`**/api/projects/${projectId}/market-comparisons/latest`)
    await page.route(
      `**/api/projects/${projectId}/market-comparisons/latest`,
      (route) =>
        route.fulfill({
          contentType: "application/json",
          body: JSON.stringify({
            comparison_id: "fx-c2",
            project_id: projectId,
            status: "ready_for_review",
            comparison_version: 2,
            research_gaps: [],
            warnings: [],
            item_count: 5,
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
            items: [1, 2, 3, 4, 5].map((n) => ({
              item_id: `fx-i${n}`,
              name: `Anbieter ${n}`,
              category: "competitor",
              description: null,
              differentiation_relevance: "Öffentlich erwähnter Unterschied.",
              relation_to_project: "competing",
              confidence_label: "source_backed",
              status: "proposed",
              source_document_ids: [`fx-s${n}`],
              evidence_quotes: [
                {
                  quote: `Zitat ${n}.`,
                  source_document_id: `fx-s${n}`,
                  source_version_id: "v1",
                },
              ],
            })),
          }),
        })
    )
    await page.goto(`/editor?field=${VC}`)
    await page.getByRole("button", { name: "Prüfen", exact: true }).click()
    await page.getByRole("tab", { name: "Markt & Wettbewerb" }).click()
    await expect(page.getByText("5 geprüfte Quellen")).toBeVisible({ timeout: 20_000 })
    await expect(page.getByText("5 Lösungen gefunden")).toBeVisible()
    await expect(page.getByText(/Vergleich erstellen/)).toHaveCount(0)
    await page.getByRole("button", { name: "Details öffnen" }).click()
    await expect(page.getByText("Markt- und Konkurrenzvergleich (Detail)").or(
      page.getByRole("dialog")
    ).first()).toBeVisible({ timeout: 20_000 })
    // runId wird nur fürs Setup gebraucht; Referenz vermeidet Lint-Warnung.
    expect(runId).toBeTruthy()
  })
})
