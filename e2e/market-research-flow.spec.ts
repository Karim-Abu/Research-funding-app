import { test, expect, type Page } from "@playwright/test"

// R8 — Markt-/Webrecherche im normalen Analyse- und Entwurfsfluss (Fake-Provider,
// deterministisch): der Dialog zeigt jede geplante Suchanfrage → eine wird bearbeitet
// (Firewall prüft neu; Budget in Zahlwörtern wird entfernt; alte Freigabe invalidiert)
// → Freigaben erteilt → «Analyse starten» → die Recherche-Phase führt exakt die
// freigegebenen Queries aus (Single-Use, firewall_approval_id) → Ergebnisse bleiben
// Kandidaten → «Verwerfen» ist persistiert, «Als Quelle speichern» erzeugt eine
// D0-Quelle → die strukturierte Zusammenfassung zeigt die Abschnitte mit
// Quellen-Status. Ohne Freigabe wird die Phase ehrlich übersprungen.
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

async function login(page: Page) {
  await page.goto("/login")
  await page.getByLabel("E-Mail").fill(EMAIL)
  await page.getByLabel("Passwort").fill(PASSWORD)
  await page.getByRole("button", { name: "Anmelden" }).click()
  await expect(page).toHaveURL(/\/$/, { timeout: 20_000 })
}

async function publicProjectWithSource(page: Page, title: string) {
  await page.goto("/intake")
  await page.getByLabel(/Projekttitel/).fill(title)
  await page
    .getByRole("textbox", { name: /Projektidee/ })
    .fill("Synthetisches Demo-Projekt für die integrierte Marktrecherche.")
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
  const projectId = (await page.evaluate(() =>
    window.sessionStorage.getItem("rf_active_project_id")
  )) as string
  expect(projectId).toBeTruthy()

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
        modules: ["market_growth", "competition_alternatives", "customer_problem"],
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
  return { projectId, csrf, mut }
}

async function completedRunId(page: Page, projectId: string): Promise<string> {
  await expect(
    page
      .getByText("Analyse läuft")
      .or(page.getByText(/Analyse (teilweise )?abgeschlossen/))
      .first()
  ).toBeVisible({ timeout: 20_000 })
  // Das Banner erscheint optimistisch VOR der Antwort auf POST /runs — die
  // Run-Liste daher pollen, bis der Lauf tatsächlich angelegt ist.
  let runId = ""
  for (let i = 0; i < 60; i++) {
    const runs = await (
      await page.request.get(`/api/projects/${projectId}/runs`)
    ).json()
    if (runs.items?.length) {
      runId = runs.items[0].run_id as string
      break
    }
    await page.waitForTimeout(500)
  }
  expect(runId).toBeTruthy()
  let status = ""
  for (let i = 0; i < 60; i++) {
    status = (await (await page.request.get(`/api/runs/${runId}`)).json()).status
    if (["completed", "failed", "stopped", "cancelled"].includes(status)) break
    await page.waitForTimeout(500)
  }
  expect(status).toBe("completed")
  return runId
}

test("Query-Freigabe, Recherche im Lauf, Verwerfen/Übernahme, Zusammenfassung", async ({
  page,
}) => {
  test.setTimeout(180_000)
  await login(page)
  const { projectId, csrf } = await publicProjectWithSource(
    page,
    "E2E Marktrecherche"
  )

  // 1. Dialog: Web-Toggle → jede geplante Suchanfrage ist sichtbar.
  await page.getByRole("button", { name: "Analyse starten" }).click()
  const dialog = page.getByRole("dialog")
  await dialog.getByRole("switch", { name: /Öffentliche Webrecherche/ }).click()
  const list = dialog.getByTestId("query-approval-list")
  await expect(list).toBeVisible({ timeout: 20_000 })
  const rows = list.getByTestId("query-approval-row")
  await expect(rows.first()).toBeVisible()

  // 2a. Bearbeiten mit NEUEN Fachbegriffen ausserhalb des geprüften Briefs
  //     wird abgelehnt — fremdes Vokabular muss zuerst in den Brief (kein
  //     stiller Bypass der Brief-Prüfung).
  await rows.nth(0).getByRole("button", { name: "Bearbeiten" }).click()
  await dialog
    .getByTestId("query-edit-input")
    .fill("Anlagenmarkt Automatisierung eine halbe Million Franken")
  await rows
    .nth(0)
    .getByRole("button", { name: "Prüfen und übernehmen" })
    .click()
  await expect(
    dialog.getByText(/Suchanfrage konnte nicht geprüft werden/)
  ).toBeVisible({ timeout: 20_000 })

  // 2b. Bearbeiten mit Brief-Vokabular wird geprüft übernommen — angezeigt
  //     (und später ausgeführt) wird nur der geprüfte Text.
  await dialog
    .getByTestId("query-edit-input")
    .fill("Energiemanagement Prognosesoftware Verteilnetzbetreiber Schweiz")
  await rows
    .nth(0)
    .getByRole("button", { name: "Prüfen und übernehmen" })
    .click()
  await expect(rows.nth(0)).toContainText(
    "Energiemanagement Prognosesoftware Verteilnetzbetreiber Schweiz",
    { timeout: 20_000 }
  )
  await expect(rows.nth(0)).not.toContainText("Million")

  // 3. Freigeben (bearbeitete + eine geplante Query), eine ablehnen.
  await rows.nth(0).getByRole("button", { name: "Freigeben" }).click()
  await expect(rows.nth(0).getByText("Freigegeben")).toBeVisible()
  await rows.nth(1).getByRole("button", { name: "Freigeben" }).click()
  await expect(rows.nth(1).getByText("Freigegeben")).toBeVisible()
  await rows.nth(2).getByRole("button", { name: "Ablehnen" }).click()
  await expect(rows.nth(2).getByText("Abgelehnt")).toBeVisible()
  await expect(dialog.getByTestId("query-approval-count")).toContainText("2 von")

  // KI-Schalter startet je nach Capabilities-Ladezeitpunkt aus — idempotent einschalten.
  const kiSwitch = dialog.getByRole("switch", { name: /Demo-Vorschläge|KI-Unterstützung/ })
  if ((await kiSwitch.getAttribute("aria-checked")) !== "true") {
    await kiSwitch.click()
  }
  await dialog
    .getByRole("checkbox", { name: "Demo-Generator für diesen Durchlauf aktivieren" })
    .click()
  await dialog.getByRole("button", { name: "Analyse starten" }).click()
  const runId = await completedRunId(page, projectId)

  // 4. Persistierte Phase: exakt die 2 freigegebenen Queries liefen; jede Task
  //    trägt die Freigabe-Provenienz (Single-Use im Firewall-Chokepoint).
  const phases = await (
    await page.request.get(`/api/runs/${runId}/phases`)
  ).json()
  const web = (phases.phases as Array<{ phase_key: string; status: string; detail: Record<string, unknown> }>).find(
    (p) => p.phase_key === "web_research"
  )
  expect(web?.status).toBe("succeeded")
  expect(web?.detail.approved_queries as number).toBe(2)
  expect(web?.detail.web_queries as number).toBe(2)
  // Der bearbeitete Budget-Text hat den Lauf nie erreicht: die ausgeführten
  // Suchanfragen sind über die UI sichtbar gewesen und ohne Zahlwort-Budget.

  // 5. Ergebnisse sind Kandidaten; Verwerfen ist persistiert; Übernahme macht
  //    eine normale D0-Quelle daraus.
  const results = await (
    await page.request.get(`/api/projects/${projectId}/research-results`)
  ).json()
  expect(results.length).toBeGreaterThanOrEqual(2)
  expect(results.every((r: { status: string }) => r.status === "candidate")).toBe(
    true
  )
  const discarded = await page.request.post(
    `/api/research-results/${results[0].result_id}/discard`,
    { headers: { "X-CSRF-Token": csrf, Origin: ORIGIN } }
  )
  expect(discarded.status()).toBe(200)
  expect((await discarded.json()).status).toBe("rejected")
  // Demo-Ergebnisse sind KEINE Webquellen: der Import wird auch auf API-Ebene
  // ehrlich verweigert (kein Fake-Output als echte Quelle).
  const imported = await page.request.post(
    `/api/research-results/${results[1].result_id}/import`,
    {
      headers: {
        "X-CSRF-Token": csrf,
        Origin: ORIGIN,
        "Idempotency-Key": idem(),
      },
    }
  )
  expect(imported.status()).toBe(422)
  const refusal = await imported.json()
  expect(JSON.stringify(refusal)).toContain("demo_result_not_importable")
  // Es entsteht KEINE URL-Quelle aus dem Demo-Ergebnis.
  const sources = await (
    await page.request.get(`/api/projects/${projectId}/sources`)
  ).json()
  expect(sources.some((s: { type: string }) => s.type === "url")).toBe(false)
  // Verworfen bleibt verworfen (Reload/erneutes Lesen).
  const resultsAfter = await (
    await page.request.get(`/api/projects/${projectId}/research-results`)
  ).json()
  const first = resultsAfter.find(
    (r: { result_id: string }) => r.result_id === results[0].result_id
  )
  expect(first.status).toBe("rejected")

  // 6. Marktvergleich ohne echte Webquellen: die UI weist die Evidenzlücke
  //    ehrlich aus — es wird KEIN Vergleich aus Demo-Ergebnissen fabriziert.
  await page.goto("/quellen")
  const section = page.getByTestId("market-comparison-section")
  await expect(section).toBeVisible({ timeout: 20_000 })
  await section.getByRole("button", { name: /Vergleich erstellen|Neu erstellen/ }).click()
  await expect(
    section.getByText(/Demo-Recherche enthält keine echten Webquellen/)
  ).toBeVisible({ timeout: 30_000 })
  await expect(page.getByTestId("market-comparison-table")).toHaveCount(0)
  // Kein Provider-Branding in der Standard-UI.
  await expect(page.locator("body")).not.toContainText(/firecrawl|anthropic|haiku/i)

  await page.getByText("Anna Keller").first().click()
  await page.getByText("Abmelden").click()
  await expect(page).toHaveURL(/\/login/, { timeout: 20_000 })
})

test("ohne Freigabe wird die Recherche-Phase ehrlich übersprungen", async ({
  page,
}) => {
  test.setTimeout(120_000)
  await login(page)
  const { projectId } = await publicProjectWithSource(
    page,
    "E2E Marktrecherche ohne Freigabe"
  )

  await page.getByRole("button", { name: "Analyse starten" }).click()
  const dialog = page.getByRole("dialog")
  await dialog.getByRole("switch", { name: /Öffentliche Webrecherche/ }).click()
  await expect(dialog.getByTestId("query-approval-list")).toBeVisible({
    timeout: 20_000,
  })
  // Bewusst NICHTS freigeben — der Dialog sagt ehrlich, was passiert.
  await expect(
    dialog.getByText(/Die Webrecherche wird übersprungen, bis mindestens eine/)
  ).toBeVisible()
  // KI-Schalter startet je nach Capabilities-Ladezeitpunkt aus — idempotent einschalten.
  const kiSwitch = dialog.getByRole("switch", { name: /Demo-Vorschläge|KI-Unterstützung/ })
  if ((await kiSwitch.getAttribute("aria-checked")) !== "true") {
    await kiSwitch.click()
  }
  await dialog
    .getByRole("checkbox", { name: "Demo-Generator für diesen Durchlauf aktivieren" })
    .click()
  await dialog.getByRole("button", { name: "Analyse starten" }).click()
  const runId = await completedRunId(page, projectId)

  const phases = await (
    await page.request.get(`/api/runs/${runId}/phases`)
  ).json()
  const web = (phases.phases as Array<{ phase_key: string; status: string; detail: Record<string, unknown> }>).find(
    (p) => p.phase_key === "web_research"
  )
  expect(web?.status).toBe("skipped")
  expect(web?.detail.reason).toBe("approval_required")
  const results = await (
    await page.request.get(`/api/projects/${projectId}/research-results`)
  ).json()
  expect(results).toEqual([])

  await page.getByText("Anna Keller").first().click()
  await page.getByText("Abmelden").click()
  await expect(page).toHaveURL(/\/login/, { timeout: 20_000 })
})
