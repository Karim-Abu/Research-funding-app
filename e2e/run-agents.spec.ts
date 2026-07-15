import { test, expect } from "@playwright/test"

// A1/A2/A3 im normalen AnalysisRun (Fake-Provider, deterministisch):
// vereinfachter Dialog → «Analyse starten» (Cloud + Webrecherche) → echte
// Phasen sichtbar → Reload zeigt denselben Stand (persistiert) → nach dem
// Lauf existieren Feldvorschläge und Critic-Findings → der Editor zeigt den
// Vorschlag zur Prüfung und übernimmt ihn nur nach explizitem Klick.
// Benötigt: Backend mit AGENT_FAKE_PROVIDER=true WEB_RESEARCH_ENABLED=true
// WEB_RESEARCH_FAKE_PROVIDER=true; Frontend APP_BACKEND_MODE=live.
const EMAIL = process.env.E2E_EMAIL ?? "anna.keller@example.test"
const PASSWORD = process.env.E2E_PASSWORD ?? "changeme-dev-lead"
const ORIGIN = "http://localhost:3000"
const PUBLIC_CLASSIFICATION = {
  sensitivity: "public",
  origin: "synthetic",
  processing_mode: "cloud_assisted",
  web_research_mode: "validated_public",
  nda_applies: false,
}

function idem(): string {
  return Math.random().toString(36).slice(2) + Date.now().toString(36)
}

test("Analyse starten erzeugt echte Feldvorschläge und Critic-Findings", async ({
  page,
}) => {
  // Zwei volle Agenten-Läufe + Editor-Flow — braucht mehr als das
  // Standard-Timeout.
  test.setTimeout(180_000)
  // 1. Login
  await page.goto("/login")
  await page.getByLabel("E-Mail").fill(EMAIL)
  await page.getByLabel("Passwort").fill(PASSWORD)
  await page.getByRole("button", { name: "Anmelden" }).click()
  await expect(page).toHaveURL(/\/$/, { timeout: 20_000 })

  // 2. Öffentliches Projekt über das echte Intake (setzt Session + Projekt).
  await page.goto("/intake")
  await page.getByLabel(/Projekttitel/).fill("E2E Agenten-Lauf")
  await page
    .getByRole("textbox", { name: /Projektidee/ })
    .fill("Synthetisches Demo-Projekt für den integrierten Agenten-Lauf.")
  await page.getByRole("button", { name: "Ändern" }).click()
  const classDialog = page.getByRole("dialog")
  await classDialog.getByText("Öffentlich", { exact: true }).click()
  await classDialog.getByRole("button", { name: "Fertig" }).click()
  await expect(classDialog).toBeHidden()
  await page.getByRole("button", { name: "Projekt erstellen und weiter" }).click()
  await expect(page).toHaveURL(/\/quellen/, { timeout: 20_000 })

  const session = await page.request.get("/api/session")
  const csrf = (await session.json()).csrf_token as string
  const mut = () => ({
    "X-CSRF-Token": csrf,
    Origin: ORIGIN,
    "Idempotency-Key": idem(),
    "Content-Type": "application/json",
  })
  const projectId = await page.evaluate(() =>
    window.sessionStorage.getItem("rf_active_project_id")
  )
  expect(projectId).toBeTruthy()

  // 3. Quelle via API (schnell + deterministisch), dann Seite neu laden.
  const src = await page.request.post(
    `/api/projects/${projectId}/sources/text`,
    {
      headers: mut(),
      data: {
        name: "Projektnotiz",
        text:
          "Der Umsetzungspartner ist in der Schweiz wertschöpfend tätig. " +
          "Ein beitragsberechtigter Forschungspartner ist eingebunden.",
        data_classification: PUBLIC_CLASSIFICATION,
      },
    }
  )
  expect((await src.json()).status).toBe("processed")

  // Query-Planung setzt seit dem Brief-Gate einen freigegebenen public-safe
  // Recherchebrief voraus (API-Setup; zwei Module ⇒ zwei geplante Queries).
  const briefResponse = await page.request.put(
    `/api/projects/${projectId}/research-brief`,
    {
      headers: mut(),
      data: {
        application_domain: "Energiemanagement",
        technology_class: "Prognosesoftware",
        target_customer_segments: ["Verteilnetzbetreiber"],
        region: "Schweiz",
        competence_needs: ["Energiedatenanalyse"],
        modules: ["market_growth", "competition_alternatives"],
      },
    }
  )
  expect(briefResponse.ok()).toBeTruthy()
  const briefId = (await briefResponse.json()).research_brief_id as string
  expect(
    (
      await page.request.post(`/api/research-briefs/${briefId}/approve`, {
        headers: mut(),
      })
    ).ok()
  ).toBeTruthy()
  await page.reload()

  // 4. Vereinfachter Dialog: Cloud-Freigabe + öffentliche Webrecherche.
  await page.getByRole("button", { name: "Analyse starten" }).click()
  const dialog = page.getByRole("dialog")
  await expect(
    dialog.getByText("Projektunterlagen analysieren")
  ).toBeVisible()
  await expect(dialog.getByText(/Dummy/)).toHaveCount(0)
  await dialog
    .getByRole("switch", { name: /Öffentliche Webrecherche/ })
    .click()
  // R8 Freigabepflicht: jede ausgehende Suchanfrage wird gesehen und einzeln
  // freigegeben — ohne Freigabe würde die Recherche-Phase übersprungen.
  const approvalList = dialog.getByTestId("query-approval-list")
  await expect(approvalList).toBeVisible({ timeout: 20_000 })
  const approvalRows = approvalList.getByTestId("query-approval-row")
  await approvalRows.nth(0).getByRole("button", { name: "Freigeben" }).click()
  await expect(approvalRows.nth(0).getByText("Freigegeben")).toBeVisible()
  await approvalRows.nth(1).getByRole("button", { name: "Freigeben" }).click()
  await expect(approvalRows.nth(1).getByText("Freigegeben")).toBeVisible()
  await expect(dialog.getByTestId("query-approval-count")).toContainText(
    "2 von"
  )
  // KI-Schalter startet je nach Capabilities-Ladezeitpunkt aus — idempotent einschalten.
  const kiSwitch = dialog.getByRole("switch", { name: /Demo-Vorschläge|KI-Unterstützung/ })
  if ((await kiSwitch.getAttribute("aria-checked")) !== "true") {
    await kiSwitch.click()
  }
  await dialog
    .getByRole("checkbox", { name: "Demo-Generator für diesen Durchlauf aktivieren" })
    .click()
  await dialog.getByRole("button", { name: "Analyse starten" }).click()

  // 5. Der Fake-Lauf ist sehr schnell: entweder ist die laufende Anzeige kurz
  // sichtbar oder der Lauf ist bereits ehrlich abgeschlossen — danach MUSS
  // der Abschluss-Banner mit den technischen Details erscheinen. (Die
  // Phasen-Darstellung selbst ist durch Component-Tests + die Phasen-API
  // unten abgedeckt.)
  await expect(
    page
      .getByText("Analyse läuft")
      .or(page.getByText(/Analyse (teilweise )?abgeschlossen/))
      .first()
  ).toBeVisible({ timeout: 20_000 })
  await expect(
    page.getByText(/Analyse (teilweise )?abgeschlossen/)
  ).toBeVisible({ timeout: 30_000 })
  await expect(page.getByText("Technische Details")).toBeVisible()
  // Run-ID erscheint erst nach dem Aufklappen (CLAUDEX: nur eingeklappt).
  await expect(page.getByText("Run-ID:")).toHaveCount(0)
  await page.getByRole("button", { name: "Technische Details" }).click()
  await expect(page.getByText("Run-ID:")).toBeVisible()

  const runs = await (
    await page.request.get(`/api/projects/${projectId}/runs`)
  ).json()
  const runId = runs.items[0].run_id as string
  expect(
    (await (await page.request.get(`/api/runs/${runId}`)).json()).status
  ).toBe("completed")

  // 8. Persistierte Phasen: alle terminal; Vorschläge + Webrecherche echt.
  const phasesBody = await (
    await page.request.get(`/api/runs/${runId}/phases`)
  ).json()
  const byKey = Object.fromEntries(
    (phasesBody.phases as Array<{ phase_key: string; status: string; detail: Record<string, unknown> }>).map(
      (p) => [p.phase_key, p]
    )
  )
  expect(Object.keys(byKey)).toHaveLength(6)
  for (const phase of Object.values(byKey)) {
    expect(["succeeded", "failed", "skipped"]).toContain(phase.status)
  }
  expect(byKey.draft_fields.status).toBe("succeeded")
  expect(
    byKey.draft_fields.detail.suggestions_created as number
  ).toBeGreaterThanOrEqual(1)
  expect(byKey.web_research.status).toBe("succeeded")
  // R8: es liefen exakt die 2 freigegebenen Suchanfragen — keine mehr.
  expect(byKey.web_research.detail.approved_queries as number).toBe(2)
  expect(byKey.web_research.detail.web_queries as number).toBe(2)
  expect(byKey.quality_review.status).toBe("succeeded")
  // Technische Zusammenfassung nennt A2 UND A3 — beide liefen im Lauf.
  const agentIds = (phasesBody.technical.agents as Array<{ agent_id: string }>).map(
    (a) => a.agent_id
  )
  expect(agentIds).toContain("A2")
  expect(agentIds).toContain("A3")

  // 9. Critic-Findings (source=agent) sind im Review-Paket sichtbar.
  const review = await (
    await page.request.get(`/api/runs/${runId}/review`)
  ).json()
  const agentFindings = (review.findings as Array<{ profile_id: string }>).filter(
    (f) => f.profile_id === "A3.evidence_consistency"
  )
  expect(agentFindings.length).toBeGreaterThanOrEqual(1)

  // 11. Editor (Deep-Link auf ein A2-Feld): Vorschlag aus der Analyse —
  // Prüfung nötig, nie Auto-Apply. Der KI-Bereich ist eingeklappt und wird
  // über «KI-Assist öffnen» sichtbar.
  await page.goto("/editor?field=INTRO.APP.ABSTRACT")
  await page
    .getByRole("button", { name: "Vorschläge", exact: true })
    .click({ timeout: 20_000 })
  await expect(page.getByTestId("run-suggestion-hint")).toBeVisible({
    timeout: 20_000,
  })
  const abstractBefore = await (
    await page.request.get(`/api/runs/${runId}/fields/INTRO.APP.ABSTRACT`)
  ).json()
  expect(abstractBefore.current_version.created_by).toBe("template")

  await page.getByRole("button", { name: "Vorschlag anzeigen" }).click()
  await page.getByRole("button", { name: "Übernehmen", exact: true }).click()
  // Übernahme abgeschlossen: der Editor meldet die nötige erneute Prüfung.
  await expect(
    page.getByText(/erneute Prüfung ist vor der Freigabe erforderlich/)
  ).toBeVisible({ timeout: 20_000 })
  await expect(page.getByTestId("run-suggestion-hint")).toHaveCount(0)
  const abstractAfter = await (
    await page.request.get(`/api/runs/${runId}/fields/INTRO.APP.ABSTRACT`)
  ).json()
  expect(abstractAfter.current_version.created_by).toBe("agent")

  // 12. Reload WÄHREND eines Laufs zeigt denselben Stand weiter (persistierte
  // Phasen): zweiter Lauf starten, sofort neu laden, Anzeige läuft weiter
  // (oder der Lauf ist bereits ehrlich abgeschlossen).
  // Nach der Navigation ist der Seitenzustand frisch — der Startknopf heisst
  // wieder «Analyse starten».
  await page.goto("/quellen")
  await page.getByRole("button", { name: "Analyse starten" }).click()
  const dialog2 = page.getByRole("dialog")
  // KI-Schalter startet je nach Capabilities-Ladezeitpunkt aus — idempotent einschalten.
  const kiSwitch2 = dialog2.getByRole("switch", { name: /Demo-Vorschläge|KI-Unterstützung/ })
  if ((await kiSwitch2.getAttribute("aria-checked")) !== "true") {
    await kiSwitch2.click()
  }
  await dialog2
    .getByRole("checkbox", { name: "Demo-Generator für diesen Durchlauf aktivieren" })
    .click()
  await dialog2.getByRole("button", { name: "Analyse starten" }).click()
  await expect(
    page
      .getByText("Analyse läuft")
      .or(page.getByText(/Analyse (teilweise )?abgeschlossen/))
      .first()
  ).toBeVisible({ timeout: 20_000 })
  // Erst neu laden, wenn der zweite Lauf tatsächlich angelegt ist — ein
  // Reload davor würde nur die Start-Requests der Seite abbrechen.
  let run2Id = ""
  for (let i = 0; i < 40; i++) {
    const items = (
      await (await page.request.get(`/api/projects/${projectId}/runs`)).json()
    ).items as Array<{ run_id: string }>
    const fresh = items.find((r) => r.run_id !== runId)
    if (fresh) {
      run2Id = fresh.run_id
      break
    }
    await page.waitForTimeout(250)
  }
  expect(run2Id).toBeTruthy()
  await page.reload()
  // Läuft der Lauf noch, nimmt die Seite die Anzeige wieder auf; ist der
  // schnelle Fake-Lauf schon fertig, zeigt sie den frischen Startzustand —
  // beides ehrlich, nichts hängt.
  await expect(
    page
      .getByText("Analyse läuft")
      .or(page.getByText(/Analyse (teilweise )?abgeschlossen/))
      .or(page.getByRole("button", { name: "Analyse starten" }))
      .first()
  ).toBeVisible({ timeout: 20_000 })
  // Persistenz-Beweis unabhängig vom Banner-Timing: die Phasen des zweiten
  // Laufs liegen nach dem Reload vollständig und terminal in der DB.
  let status2 = ""
  for (let i = 0; i < 60; i++) {
    status2 = (
      await (await page.request.get(`/api/runs/${run2Id}`)).json()
    ).status
    if (["completed", "failed", "stopped", "cancelled"].includes(status2))
      break
    await page.waitForTimeout(500)
  }
  expect(status2).toBe("completed")
  const phases2 = await (
    await page.request.get(`/api/runs/${run2Id}/phases`)
  ).json()
  expect((phases2.phases as Array<{ status: string }>).length).toBe(6)
  for (const p of phases2.phases as Array<{ status: string }>) {
    expect(["succeeded", "failed", "skipped"]).toContain(p.status)
  }

  await page.getByText("Anna Keller").first().click()
  await page.getByText("Abmelden").click()
  await expect(page).toHaveURL(/\/login/, { timeout: 20_000 })
})
