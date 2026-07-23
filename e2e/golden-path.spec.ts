import { test, expect, type Page } from "@playwright/test"
import {
  choosePublic,
  FIXTURE_PDF,
  getActiveProjectId,
  login,
  logout,
  mutFactory,
  waitForRecheckCleared,
  waitForRunCompleted,
} from "./helpers"

// TECHNISCHER E2E (Ebene A — deterministisch, Fake-LLM + Fake-Webprovider,
// ohne externe Schlüssel). Beweist UI-/Persistenztechnik des Golden Path —
// NICHT die fachliche Auslese-Qualität (dafür: e2e/import-functional.spec.ts)
// und NICHT die Statuswahrheit (dafür: e2e/review-truth.spec.ts).
// Ablauf: Login → Projekt aus Idee + Innolink-PDF → Importkandidaten
// prüfen/übernehmen → Partner → Budget + Regeln → Recherchebrief freigeben →
// Analyse starten → sichere Research-Queries genehmigen → Demo-Recherche
// ehrlich anzeigen (kein Fake-Import, kein fabrizierter Marktvergleich) →
// A2-Vorschläge + A3-Findings ansehen → ein Feld bearbeiten und freigeben →
// Qualitätsprüfung → Feld in der Innolink-Kopieransicht kopieren → Browser
// neu laden (Zustand bleibt) → Abmelden.
//
// Der Projekttitel trägt einen Zeitstempel, damit der Test ZWEIMAL hintereinander auf
// derselben Demo-DB läuft (Akzeptanzkriterium). Benötigt: Backend mit
// AGENT_FAKE_PROVIDER=true WEB_RESEARCH_ENABLED=true WEB_RESEARCH_FAKE_PROVIDER=true
// DEMO_DATA_ENABLED=true; Frontend APP_BACKEND_MODE=live.
test.use({ permissions: ["clipboard-read", "clipboard-write"] })

const ABSTRACT = "INTRO.APP.ABSTRACT"
const SOLUTION = "SOL.INNOVATION_SOLUTION.EDITOR"
const EDITED_ABSTRACT = "Kurzfassung ohne Platzhalter für den Golden Path."

// Die Zwischenablage kann Zeilenenden/Randleerzeichen umschreiben — auf dieser Basis
// vergleichen (identisch zum Muster in portal-transfer.spec.ts).
function normalize(s: string): string {
  return s
    .replace(/\r\n/g, "\n")
    .split("\n")
    .map((l) => l.replace(/[ \t]+$/, ""))
    .join("\n")
    .trim()
}

async function copyCard(page: Page, fieldName: string): Promise<void> {
  const card = page.locator("article", {
    has: page.getByRole("heading", { name: fieldName, exact: true }),
  })
  const plainCopy = card.getByRole("button", { name: "Text kopieren" })
  if (await plainCopy.isVisible().catch(() => false)) {
    await plainCopy.click()
  } else {
    await card.getByRole("button", { name: "Trotzdem kopieren…" }).click()
    const reason = card.getByText("Feld wird im Portal fertiggestellt")
    if (await reason.isVisible().catch(() => false)) await reason.click()
  }
  const confirm = card.getByRole("button", { name: "Trotzdem kopieren", exact: true })
  if (await confirm.isVisible().catch(() => false)) await confirm.click()
  await expect(card.getByText(/Kopiert am/)).toBeVisible()
}

test("Technischer E2E (Fake-Provider): Idee + PDF bis Innolink-Kopieransicht, Zustand übersteht Reload", async ({
  page,
}) => {
  test.setTimeout(300_000)
  const title = `Golden Path ${Date.now()}`

  await test.step("1. Login", async () => {
    await login(page)
  })

  await test.step("2.–3. Neues Projekt: Idee + Innolink-PDF hochladen", async () => {
    await page.goto("/intake")
    await page.getByLabel(/Projekttitel/).fill(title)
    await page
      .getByRole("textbox", { name: /Projektidee/ })
      .fill("Synthetisches Demo-Projekt für den Golden Path (Idee + PDF).")
    await page.getByTestId("intake-file-input").setInputFiles(FIXTURE_PDF)
    await expect(page.getByLabel(/Projekttitel/)).toHaveValue(title)
    await choosePublic(page)
    await page.getByRole("button", { name: "Projekt erstellen und weiter" }).click()
    // Ein erkanntes Innolink-PDF führt in die Import-Review.
    await expect(page).toHaveURL(/\/import\?source=/, { timeout: 20_000 })
  })

  const projectId = await getActiveProjectId(page)

  await test.step("4. Importkandidaten prüfen und Abstract übernehmen", async () => {
    await expect(page.getByTestId("import-review")).toBeVisible({ timeout: 60_000 })
    await expect(page.getByTestId("import-candidate")).toHaveCount(8)
    // Nichts ist vorentschieden; unsichere Felder sind markiert (HITL).
    await expect(page.getByText("Übernommen", { exact: true })).toHaveCount(0)
    const abstractRow = page
      .getByTestId("import-candidate")
      .filter({ hasText: "Abstract" })
      .first()
    await abstractRow.getByRole("button", { name: "Übernehmen", exact: true }).click()
    await expect(abstractRow.getByText("Übernommen", { exact: true })).toBeVisible({
      timeout: 20_000,
    })
  })

  await test.step("5. Partner ergänzen", async () => {
    const mut = await mutFactory(page)
    const dates = await page.request.patch(`/api/projects/${projectId}`, {
      headers: mut(),
      data: { start_date: "2026-01-01", end_date: "2027-12-31" },
    })
    expect(dates.status()).toBe(200)
    await page.goto("/partner")
    const addPartner = page.getByRole("button", { name: "Partner hinzufügen" })

    async function fillPartner(name: string, role: string): Promise<void> {
      // exact: das Feld «Offizielle Vertretung – nur Name …» enthält sonst
      // ebenfalls «Name».
      await page.getByLabel("Name", { exact: true }).fill(name)
      await page.getByLabel("Land").fill("CH")
      await page.getByLabel("Rolle im Projekt").fill(role)
      await page
        .getByLabel("Kompetenz & Beitrag (kurz)")
        .fill("Einschlägige Kompetenz für den Golden-Path-Demo-Workflow.")
    }

    await fillPartner("ETH Zürich", "Grundlagenforschung")
    await addPartner.click()
    await expect(page.getByText("ETH Zürich").first()).toBeVisible({ timeout: 20_000 })
    await fillPartner("Industrie AG", "Umsetzung und Pilotierung")
    await addPartner.click()
    await expect(page.getByText("Industrie AG").first()).toBeVisible({ timeout: 20_000 })
  })

  await test.step("6. Budget erfassen und Regeln sehen", async () => {
    await page.getByLabel("Direkte Projektkosten (ohne Overhead)").fill("100000")
    await page.getByLabel("Eigenleistung Umsetzungspartner").fill("45000")
    await page.getByLabel("Barbeitrag (Cash)").fill("5000")
    await expect(page.getByText("24 Monate", { exact: true })).toBeVisible()
    await page.getByRole("button", { name: "Budget speichern" }).click()
    await expect(page.getByText("Budgetangaben gespeichert.")).toBeVisible({
      timeout: 20_000,
    })
    // Regeln erscheinen sofort (Backend-Rule-Kern): 50 % Umsetzung + 5 % Cash → Erfüllt.
    const precheck = page.getByTestId("budget-precheck")
    await expect(precheck.getByText("Erfüllt", { exact: true })).toHaveCount(2, {
      timeout: 20_000,
    })
  })

  let runId = ""
  await test.step("7.–8. Analyse starten und sichere Research-Queries genehmigen", async () => {
    await page.goto("/quellen")
    // Queries entstehen nur aus dem geprüften öffentlichen Recherchebrief —
    // zuerst vorschlagen lassen und public-safe freigeben (HITL).
    const research = page.getByTestId("public-research-panel")
    await expect(research).toBeVisible({ timeout: 20_000 })
    await research
      .getByRole("button", { name: "Recherchebrief vorschlagen" })
      .click()
    await expect(page.getByTestId("research-brief-form")).toBeVisible({
      timeout: 20_000,
    })
    // Vereinfachtes public-safe Ziel (keine Rohidee, Partnernamen oder Budgets).
    await page
      .getByLabel("Recherchefrage / Ziel")
      .fill("Prognosesoftware für Energiemanagement bei Schweizer Verteilnetzbetreibern")
    await page.getByRole("button", { name: "Public-safe Brief freigeben" }).click()
    await expect(page.getByText(/Brief v\d+ freigegeben/)).toBeVisible({
      timeout: 20_000,
    })
    await page.getByRole("button", { name: "Analyse starten" }).click()
    const dialog = page.getByRole("dialog")
    await dialog.getByRole("switch", { name: /Öffentliche Webrecherche/ }).click()
    const list = dialog.getByTestId("query-approval-list")
    await expect(list).toBeVisible({ timeout: 20_000 })
    const rows = list.getByTestId("query-approval-row")
    await expect(rows.first()).toBeVisible()
    // HITL — jede ausgehende Query wird gesehen: erste freigeben, letzte
    // (falls der Brief-Planer mehrere Queries erzeugt) bewusst ablehnen.
    const rowCount = await rows.count()
    await rows.nth(0).getByRole("button", { name: "Freigeben" }).click()
    await expect(rows.nth(0).getByText("Freigegeben")).toBeVisible()
    if (rowCount >= 2) {
      await rows
        .nth(rowCount - 1)
        .getByRole("button", { name: "Ablehnen" })
        .click()
      await expect(rows.nth(rowCount - 1).getByText("Abgelehnt")).toBeVisible()
    }
    // Fake-Modus: Bestätigung des Demo-Generators (ehemals «Cloud-KI erlauben»).
    // Der KI-Schalter startet je nach Capabilities-Ladezeitpunkt aus —
    // idempotent einschalten, dann bestätigen.
    const kiSwitch = dialog.getByRole("switch", {
      name: /Demo-Vorschläge|KI-Unterstützung/,
    })
    if ((await kiSwitch.getAttribute("aria-checked")) !== "true") {
      await kiSwitch.click()
    }
    await dialog
      .getByRole("checkbox", { name: "Demo-Generator für diesen Durchlauf aktivieren" })
      .click()
    await dialog.getByRole("button", { name: "Analyse starten" }).click()
    runId = await waitForRunCompleted(page, projectId)
  })

  await test.step("9. Demo-Recherche ehrlich anzeigen und Marktvergleich prüfen", async () => {
    // Freigegebene Brief-Queries ausführen: Ergebnisse sind im Fake-Modus
    // klar als «Demo» markiert und können NICHT als Quelle übernommen werden
    // (kein Fake-Output als echte Webquelle — Bindungsregel).
    const research = page.getByTestId("public-research-panel")
    await expect(research).toBeVisible({ timeout: 20_000 })
    // Die im Analyse-Dialog freigegebenen Queries sind nach dem Lauf
    // verbraucht (single-use) — für die Panel-Recherche neue Queries aus dem
    // freigegebenen Brief erzeugen und einzeln freigeben (HITL).
    await research.getByRole("button", { name: "Queries erzeugen" }).click()
    const panelRows = research.getByTestId("query-approval-row")
    await expect(panelRows.first()).toBeVisible({ timeout: 20_000 })
    // Die im Lauf verbrauchte Query steht als «Ausgeführt» in der Historie —
    // freigegeben wird die neue, noch offene Query.
    const openRow = panelRows.filter({ hasText: "Offen" }).first()
    await openRow.getByRole("button", { name: "Freigeben" }).click()
    await expect(openRow.getByText("Freigegeben")).toBeVisible({ timeout: 20_000 })
    await research
      .getByRole("button", { name: "Freigegebene Queries ausführen" })
      .click()
    const results = page.getByTestId("research-results")
    await expect(results.getByText("Demo", { exact: true }).first()).toBeVisible({
      timeout: 30_000,
    })
    await expect(
      results.getByRole("button", { name: "Übernehmen", exact: true })
    ).toHaveCount(0)

    // Markt-/Konkurrenzvergleich: im Demo-Modus gibt es keine echten
    // Webquellen — seit dem Quellen-Gate ist «Vergleich erstellen» dann
    // sichtbar deaktiviert (konkreter Grund statt eines fabrizierten leeren
    // Vergleichs; kein Fake-Output als «Marktanalyse»).
    const section = page.getByTestId("market-comparison-section")
    await expect(section).toBeVisible({ timeout: 20_000 })
    await expect(
      section.getByRole("button", { name: /Vergleich erstellen|Neu erstellen/ })
    ).toBeDisabled()
    await expect(
      section.getByTestId("market-comparison-disabled-reason")
    ).toContainText(
      "Noch keine live abgerufene, importierte und inhaltlich positiv geprüfte Quelle"
    )
    await expect(page.getByTestId("market-comparison-table")).toHaveCount(0)
  })

  await test.step("10. A2-Feldvorschläge und A3-Findings anzeigen", async () => {
    // A2: Feldvorschlag aus der Analyse — nur zur Prüfung, nie automatisch übernommen.
    await page.goto(`/editor?field=${ABSTRACT}`)
    // Editor-Modus «Vorschläge» (ehemals «KI-Assist öffnen»).
    await page
      .getByRole("button", { name: "Vorschläge", exact: true })
      .click({ timeout: 20_000 })
    await expect(page.getByTestId("run-suggestion-hint")).toBeVisible({
      timeout: 20_000,
    })

    // A3: evidenzbezogener Hinweis im Feld «Lösung & Innovation» (Modus «Prüfen»).
    await page.goto(`/editor?field=${SOLUTION}`)
    await expect(
      page.getByRole("navigation", { name: "Unterabschnitte" })
    ).toBeVisible({ timeout: 20_000 })
    await page.getByRole("button", { name: "Prüfen", exact: true }).click()
    await page.getByRole("tab", { name: "Schwächen" }).click()
    await expect(
      page.getByText(/nicht mit verifizierten Belegen verknüpft/)
    ).toBeVisible({ timeout: 20_000 })
  })

  await test.step("11. Abschnitt bearbeiten und speichern", async () => {
    await page.goto(`/editor?field=${ABSTRACT}`)
    const editor = page.getByLabel(/^Entwurf /)
    await editor.click()
    await page.keyboard.press("ControlOrMeta+A")
    await page.keyboard.press("Delete")
    await editor.pressSequentially(EDITED_ABSTRACT)
    await page.getByRole("button", { name: "Speichern" }).click()
    await expect(
      page.getByText(/erneute Prüfung ist vor der Freigabe erforderlich/)
    ).toBeVisible({ timeout: 20_000 })
  })

  await test.step("11a. Versionshistorie zeigt die neue Version (RUN 4B)", async () => {
    await page.getByRole("button", { name: "Prüfen", exact: true }).click()
    await page.getByRole("tab", { name: "Versionen" }).click()
    const rows = page.getByTestId("version-row")
    await expect(rows.first()).toBeVisible({ timeout: 20_000 })
    expect(await rows.count()).toBeGreaterThanOrEqual(2)
    await expect(rows.first()).toContainText("Manuell bearbeitet")
    await expect(page.getByText("Aktuell", { exact: true })).toBeVisible()
  })

  await test.step("12. Qualitätsprüfung durchführen", async () => {
    await page.goto("/review")
    await expect(
      page.getByRole("heading", { name: "Qualitätsprüfung", exact: true })
    ).toBeVisible({ timeout: 20_000 })
    // A3-Hinweise sind in der Prüfung sichtbar (KI-gestützte Hinweise).
    await expect(page.getByTestId("ai-findings")).toBeVisible({ timeout: 20_000 })
    await page
      .getByRole("button", { name: "Gesamte Prüfung erneut ausführen" })
      .click()
    await waitForRecheckCleared(page.request, runId)
  })

  await test.step("11b. Abschnitt freigeben", async () => {
    await page.goto(`/editor?field=${ABSTRACT}`)
    await page.getByRole("button", { name: "Prüfen", exact: true }).click()
    await page.getByRole("tab", { name: "Kommentare" }).click()
    await page.getByRole("button", { name: "Abschnitt freigeben" }).click()
    await expect(page.getByText("Abschnitt freigegeben.")).toBeVisible({
      timeout: 20_000,
    })
  })

  const abstract = (
    (await (await page.request.get(`/api/runs/${runId}/fields`)).json()) as Array<{
      field_id: string
      field_name: string
      current_version: { text: string }
    }>
  ).find((f) => f.field_id === ABSTRACT)!
  expect(abstract.current_version.text).toContain(EDITED_ABSTRACT)

  await test.step("13. Feld in der Innolink-Kopieransicht kopieren", async () => {
    await page.goto("/export")
    await page.getByRole("tab", { name: "Innolink-Kopieransicht" }).click()
    await expect(
      page.getByRole("heading", { name: "Abdeckung der Übernahmeansicht" })
    ).toBeVisible({ timeout: 20_000 })
    await copyCard(page, abstract.field_name)
    expect(normalize(await page.evaluate(() => navigator.clipboard.readText()))).toBe(
      normalize(abstract.current_version.text)
    )
    // Keine Provider-/Technikbegriffe in der Standard-UI.
    await expect(page.locator("body")).not.toContainText(
      /firecrawl|anthropic|haiku|synthetic_eval|Dummy/i
    )
  })

  await test.step("14. Browser neu laden — Zustand bleibt erhalten", async () => {
    // Reload der Kopieransicht: die Seite baut ihren Zustand aus dem Server neu auf.
    await page.reload()
    await page.getByRole("tab", { name: "Innolink-Kopieransicht" }).click()
    await expect(
      page.getByRole("heading", { name: "Abdeckung der Übernahmeansicht" })
    ).toBeVisible({ timeout: 20_000 })
    // Keine Provider-/Technikbegriffe in der Standard-UI.
    await expect(page.locator("body")).not.toContainText(
      /firecrawl|anthropic|haiku|synthetic_eval|Dummy/i
    )
    // Serverseitig persistiert: der bearbeitete Abschnitt bleibt nach dem Reload
    // erhalten (im Editor sichtbar).
    await page.goto(`/editor?field=${ABSTRACT}`)
    await expect(page.getByLabel(/^Entwurf /)).toContainText(EDITED_ABSTRACT, {
      timeout: 20_000,
    })
    const fresh = (
      (await (await page.request.get(`/api/runs/${runId}/fields`)).json()) as Array<{
        field_id: string
        current_version: { text: string }
      }>
    ).find((f) => f.field_id === ABSTRACT)!
    expect(fresh.current_version.text).toContain(EDITED_ABSTRACT)
  })

  await test.step("15. Abmelden", async () => {
    await logout(page)
  })
})
