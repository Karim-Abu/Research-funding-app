// FINAL MVP ACCEPTANCE — Browser-Abnahme der Phase-B-Lücken + Phase-C-Beweis.
// Schliesst NUR die Punkte, die kein bestehender Gate-/Opt-in-Spec abdeckt
// (B1 Primärquelle via UI, B2 Drei-Gruppen-Ansicht, B3 52 %+5 % mit
// Regelquelle, B4 Statuskatalog, B5 Belegstufen, B6 Unicode-Roundtrip,
// B7 Markt ready aus dem Evaluation-Seed, B9 vier Qualitätskategorien,
// Phase C Beleg-Details über den echten Read-Pfad). Opt-in und NIE Teil
// der Gates:
//   FINAL_ACCEPT=1 corepack pnpm exec playwright test e2e/final-acceptance.spec.ts
// Zusätzliche Screenshots (Phase D): FINAL_VISUAL=1 (nach docs/assets/final/).
// Voraussetzungen wie verify_all: lokale Server, Fake-Provider, Demo-Seed
// mit --evaluation. Keine externen Provider-Calls; alle Zustände stammen aus
// dem deterministischen Seed (keine route-Fixtures nötig).
import { execFileSync } from "node:child_process"
import { existsSync, mkdirSync } from "node:fs"
import path from "node:path"
import { expect, test, type Page } from "@playwright/test"

import { choosePublic, login, mutFactory } from "./helpers"

const FIXTURE_PDF = path.join(
  __dirname, "..", "spike", "fixtures", "innolink_sample.pdf"
)
const OUT_DIR = path.join(process.cwd(), "docs", "assets", "final")
const VIEWPORTS = [
  { width: 1440, height: 900 },
  { width: 1280, height: 800 },
  { width: 768, height: 1024 },
]
const UNICODE_GOAL =
  "KI-gestützte Datenanalyse für Schweizer KMU – Zürich/DACH (B2B)"
const STAMP = Date.now()
const B3_TITLE = `Finale Abnahme 52-5 ${STAMP}`

test.skip(
  process.env.FINAL_ACCEPT !== "1",
  "Set FINAL_ACCEPT=1 to run the final MVP acceptance browser spec."
)

test.describe.configure({ mode: "serial" })

test.beforeAll(() => {
  const backendDir = path.join(process.cwd(), "backend")
  const venvPython = path.join(backendDir, ".venv", "Scripts", "python.exe")
  const python =
    process.env.BACKEND_PYTHON ?? (existsSync(venvPython) ? venvPython : "python")
  // Eigenes Reseed mit --evaluation: die volle Suite reseedet zwischendurch
  // plain (demo-dataset.spec) und verlöre sonst die Evaluation-Anreicherung.
  execFileSync(python, ["-m", "app.demo.seed", "--reset", "--evaluation"], {
    cwd: backendDir,
    env: { ...process.env, APP_ENV: "development", DEMO_DATA_ENABLED: "true" },
    stdio: "inherit",
  })
  mkdirSync(OUT_DIR, { recursive: true })
})

async function shot(page: Page, name: string): Promise<void> {
  if (process.env.FINAL_VISUAL !== "1") return
  const current = page.viewportSize()
  for (const viewport of VIEWPORTS) {
    await page.setViewportSize(viewport)
    await page.waitForTimeout(400)
    await page.screenshot({
      path: path.join(OUT_DIR, `${name}-${viewport.width}x${viewport.height}.png`),
      fullPage: true,
    })
  }
  if (current) await page.setViewportSize(current)
}

/** Demo-Projekt über die Dashboard-Karte aktiv setzen. */
async function openProject(page: Page, heading: RegExp): Promise<void> {
  await page.goto("/")
  await page.getByRole("heading", { name: heading }).click()
  await expect(page).not.toHaveURL(/\/$/, { timeout: 20_000 })
}

test.describe("FINAL MVP ACCEPTANCE — Browser", () => {
  test("B1: Erstimport setzt die Primärquelle (Gruppe «Primärer Innolink-Antrag»)", async ({ page }) => {
    test.setTimeout(300_000)
    await login(page)
    await page.goto("/intake")
    await page.getByLabel(/Projekttitel/).fill(`Finale Abnahme Import ${STAMP}`)
    await page
      .getByRole("textbox", { name: /Projektidee/ })
      .fill("Finale Abnahme: Import-, Primärquellen- und Recherchefluss.")
    await page.getByTestId("intake-file-input").setInputFiles(FIXTURE_PDF)
    await choosePublic(page)
    await page.getByRole("button", { name: "Projekt erstellen und weiter" }).click()
    await expect(page).toHaveURL(/\/quellen/, { timeout: 30_000 })

    // Erstimport abwarten — er weist die Primärquelle implizit zu.
    await page.goto("/import")
    await expect(page.getByTestId("import-review")).toBeVisible({
      timeout: 120_000,
    })

    await page.goto("/quellen")
    const primaryGroup = page.getByTestId("source-group-primary_application")
    await expect(primaryGroup).toBeVisible({ timeout: 20_000 })
    await expect(primaryGroup.getByText("Verwendet für Import und Antragsanalyse.")).toBeVisible()
    await expect(primaryGroup.getByText(/innolink_sample/i).first()).toBeVisible()
    // Kein «kein Antrag festgelegt»-Hinweis mehr: die Quelle liegt in der Gruppe.
    await expect(
      primaryGroup.getByText(/Noch kein primärer Innolink-Antrag/)
    ).toHaveCount(0)
    test.info().annotations.push({
      type: "limitation",
      description:
        "Kein explizites UI-Control «Als Primärquelle festlegen» — die Zuweisung erfolgt implizit beim Erstimport (backend/app/imports/service.py); bei mehreren Kandidaten zeigt die UI nur den Hinweis. Dokumentiert in FINAL_MVP_LIMITATIONS.",
    })
  })

  test("B6: Rechercheziel mit Unicode überlebt Speichern + Reload", async ({ page }) => {
    test.setTimeout(240_000)
    await login(page)
    await page.goto("/intake")
    await page.getByLabel(/Projekttitel/).fill(`Finale Abnahme Recherche ${STAMP}`)
    await page
      .getByRole("textbox", { name: /Projektidee/ })
      .fill("Finale Abnahme: öffentlicher Recherche-Brief mit Unicode-Ziel.")
    await choosePublic(page)
    await page.getByRole("button", { name: "Projekt erstellen und weiter" }).click()
    await expect(page).toHaveURL(/\/quellen/, { timeout: 30_000 })

    const panel = page.getByTestId("public-research-panel")
    await expect(panel).toBeVisible({ timeout: 20_000 })
    const form = page.getByTestId("research-brief-form")
    try {
      await form.waitFor({ state: "visible", timeout: 5_000 })
    } catch {
      await panel.getByRole("button", { name: /Recherchebrief vorschlagen/ }).click()
      await form.waitFor({ state: "visible", timeout: 20_000 })
    }
    const goal = page.getByLabel("Recherchefrage / Ziel")
    await goal.fill(UNICODE_GOAL)
    await expect(goal).toHaveValue(UNICODE_GOAL)
    await page.getByRole("button", { name: "Entwurf speichern" }).click()
    // Persistenz statt UI-Zustand: Reload und exakte Wiedergabe des Inhalts.
    await page.waitForTimeout(1_000)
    await page.reload()
    await expect(page.getByTestId("public-research-panel")).toBeVisible({
      timeout: 20_000,
    })
    await expect(page.getByText(UNICODE_GOAL).first()).toBeVisible({
      timeout: 20_000,
    })
    await shot(page, "recherche-brief-unicode")
  })

  test("B3/B4: 52 % + 5 % Erfüllt mit Regelquelle; Statuskatalog vollständig", async ({ page }) => {
    test.setTimeout(300_000)
    await login(page)
    await page.goto("/intake")
    await page.getByLabel(/Projekttitel/).fill(B3_TITLE)
    await page
      .getByRole("textbox", { name: /Projektidee/ })
      .fill("Finale Abnahme: Partner, Budget 52/5 und Regelnachweise.")
    await choosePublic(page)
    await page.getByRole("button", { name: "Projekt erstellen und weiter" }).click()
    await expect(page).toHaveURL(/\/quellen/, { timeout: 30_000 })

    const projectId = await page.evaluate(() =>
      window.sessionStorage.getItem("rf_active_project_id")
    )
    expect(projectId).toBeTruthy()
    const mut = await mutFactory(page)
    // 48 Monate: bewusst ausserhalb der üblichen 6–36 → deterministisch
    // «Teilweise erfüllt» auf der Advisory-Dauerregel (B4-Statuskatalog).
    const dates = await page.request.patch(`/api/projects/${projectId}`, {
      headers: mut(),
      data: { start_date: "2026-01-01", end_date: "2029-12-31" },
    })
    expect(dates.status()).toBe(200)

    // Partner über die echte UI: 1× Umsetzungspartner (CH, Wertschöpfung
    // bestätigt) + 1× Forschungspartner (beitragsberechtigt).
    await page.goto("/partner")
    const addPartner = page.getByRole("button", { name: "Partner hinzufügen" })
    await page.getByLabel("Name", { exact: true }).fill("Alpina Umsetzung AG (Test)")
    await page.getByLabel("Partnertyp").selectOption("implementation_partner")
    await page.getByLabel("Land").fill("CH")
    await page.getByLabel("Rolle im Projekt").fill("Pilotierung und Umsetzung")
    await page
      .getByLabel("Kompetenz & Beitrag (kurz)")
      .fill("Pilotanlage und Industrialisierung für die finale Abnahme.")
    await page.getByLabel("Wertschöpfung in der Schweiz").selectOption("true")
    await addPartner.click()
    await expect(page.getByText("Alpina Umsetzung AG (Test)").first()).toBeVisible({
      timeout: 20_000,
    })
    await page.getByLabel("Name", { exact: true }).fill("Institut für Systeme (Test)")
    await page.getByLabel("Partnertyp").selectOption("research_partner")
    await page.getByLabel("Land").fill("CH")
    await page.getByLabel("Rolle im Projekt").fill("Forschung und Validierung")
    await page
      .getByLabel("Kompetenz & Beitrag (kurz)")
      .fill("Wissenschaftliche Begleitung für die finale Abnahme.")
    await page.getByLabel("Beitragsberechtigung").selectOption("eligible")
    await addPartner.click()
    await expect(
      page.getByText("Institut für Systeme (Test)").first()
    ).toBeVisible({ timeout: 20_000 })

    // Budget: 47k Eigenleistung + 5k Cash von 100k = exakt 52 % + 5 %.
    await page.getByLabel("Direkte Projektkosten (ohne Overhead)").fill("100000")
    await page.getByLabel("Eigenleistung Umsetzungspartner").fill("47000")
    await page.getByLabel("Barbeitrag (Cash)").fill("5000")
    await expect(page.getByText("48 Monate", { exact: true })).toBeVisible()
    await page.getByRole("button", { name: "Budget speichern" }).click()
    await expect(page.getByText("Budgetangaben gespeichert.")).toBeVisible({
      timeout: 20_000,
    })

    // B3: beide Prechecks fachlich «Erfüllt», 52 % und 5 % sichtbar.
    const precheck = page.getByTestId("budget-precheck")
    await expect(precheck.getByText("Erfüllt", { exact: true })).toHaveCount(2, {
      timeout: 20_000,
    })
    await expect(precheck.getByTestId("precheck-contribution")).toContainText("52")
    await expect(precheck.getByTestId("precheck-cash")).toContainText("5 %")
    // Offizielle Quelle + Regelstand direkt am Precheck.
    await page.getByRole("button", { name: "Warum wird das geprüft?" }).click()
    await expect(precheck.getByText(/Quelle: /).first()).toBeVisible()
    await expect(precheck.getByText(/Regelstand /).first()).toBeVisible()
    await shot(page, "partner-budget-precheck-52-5")

    // Quelle + Lauf (deterministisch) über die API vorbereiten.
    const src = await page.request.post(`/api/projects/${projectId}/sources/text`, {
      headers: mut(),
      data: {
        name: "Abnahme-Notiz",
        text: "Inhalt für den deterministischen Abnahme-Lauf.",
        data_classification: {
          sensitivity: "public",
          origin: "synthetic",
          processing_mode: "deterministic_only",
          web_research_mode: "off",
          nda_applies: false,
        },
      },
    })
    expect((await src.json()).status).toBe("processed")
    const runRes = await page.request.post(`/api/projects/${projectId}/runs`, {
      headers: mut(),
      data: {
        settings: {
          processing_mode: "deterministic_only",
          max_cost_chf: 0,
          max_llm_calls: 0,
          max_web_calls: 0,
        },
      },
    })
    expect(runRes.status()).toBe(202)
    const accepted = await runRes.json()
    let opStatus = ""
    for (let i = 0; i < 60; i++) {
      const op = await page.request.get(`/api/operations/${accepted.operation_id}`)
      opStatus = (await op.json()).status
      if (["succeeded", "failed", "cancelled"].includes(opStatus)) break
      await page.waitForTimeout(500)
    }
    expect(opStatus).toBe("succeeded")

    // Beide Budget-Anforderungen fachlich fulfilled — Review nur sekundär,
    // keine Herabstufung (Mandat B3).
    const reqRes = await page.request.get(
      `/api/runs/${accepted.resource_id}/requirements`
    )
    expect(reqRes.status()).toBe(200)
    const byId = Object.fromEntries(
      ((await reqRes.json()) as Array<{ requirement_id: string; status: string }>).map(
        (a) => [a.requirement_id, a.status]
      )
    )
    expect(byId["REQ.INNO.BUDGET.IMPLEMENTATION_SHARE_40_60"]).toBe("fulfilled")
    expect(byId["REQ.INNO.BUDGET.CASH_MIN5"]).toBe("fulfilled")
    expect(byId["REQ.INNO.DURATION.TYPICAL_6_36"]).toBe("partial")

    // B4 im selben Projekt: Erfüllt / Teilweise erfüllt / Nicht beurteilbar /
    // Hinweise; keine rohen Regel-IDs im Standardfluss.
    await page.goto("/anforderungen")
    await expect(page.getByText("Fördervoraussetzungen").first()).toBeVisible({
      timeout: 20_000,
    })
    await expect(page.getByText("Erfüllt", { exact: true }).first()).toBeVisible()
    await expect(
      page.getByText("Teilweise erfüllt", { exact: true }).first()
    ).toBeVisible()
    await expect(
      page.getByText("Nicht beurteilbar", { exact: true }).first()
    ).toBeVisible()
    await expect(
      page.getByRole("heading", { name: "Hinweise", exact: true })
    ).toBeVisible()
    await expect(page.getByText(/REQ\.INNO\./).first()).not.toBeVisible()
    await expect(page.getByText(/INTRO\.APP\./).first()).not.toBeVisible()

    // B3: Regelgrundlage mit offizieller Quelle + Link in der Detailansicht.
    const rows = page.locator('[id^="req-"] > button')
    const rowCount = await rows.count()
    let ruleEvidenceFound = false
    for (let i = 0; i < rowCount; i++) {
      await rows.nth(i).click()
      const evidence = page.getByTestId("rule-evidence")
      if (await evidence.first().isVisible().catch(() => false)) {
        await expect(evidence.getByText("Regelgrundlage").first()).toBeVisible()
        await expect(evidence.getByText(/Quelle:/).first()).toBeVisible()
        const link = evidence
          .getByRole("link", { name: "Offizielle Regel öffnen" })
          .first()
        await expect(link).toBeVisible()
        expect(await link.getAttribute("href")).toBeTruthy()
        ruleEvidenceFound = true
        break
      }
      await rows.nth(i).click()
    }
    expect(ruleEvidenceFound).toBe(true)
    await shot(page, "anforderungen-statuskatalog")

    // «Nicht erfüllt» (verletztes Hard Gate): Demo-Projekt B ohne
    // Forschungspartner.
    await openProject(page, /Produktionsanlagen \(Demo\)/)
    await page.goto("/anforderungen")
    await expect(page.getByText("Fördervoraussetzungen").first()).toBeVisible({
      timeout: 20_000,
    })
    await expect(
      page.getByText("Nicht erfüllt", { exact: true }).first()
    ).toBeVisible()
    // «Nicht geprüft» (not_run) ist über die Prüfstatus-Ansicht abgedeckt
    // (review-truth.spec: eigenes Segment, nie grün) und in B9 unten.
  })

  test("B2: Quellen in drei Zweck-Gruppen; Projektunterlagen nie als Antragsquelle", async ({ page }) => {
    test.setTimeout(180_000)
    await login(page)
    await openProject(page, /Verbundwerkstoffe \(Demo\)/)
    await page.goto("/quellen")
    await expect(page.getByTestId("source-groups")).toBeVisible({ timeout: 20_000 })

    const primary = page.getByTestId("source-group-primary_application")
    const documents = page.getByTestId("source-group-project_documents")
    const research = page.getByTestId("source-group-public_research")
    await expect(primary).toBeVisible()
    await expect(documents).toBeVisible()
    await expect(research).toBeVisible()
    await expect(primary.getByText("Verwendet für Import und Antragsanalyse.")).toBeVisible()
    await expect(documents.getByText("Verwendet als Entwurfskontext.")).toBeVisible()
    await expect(
      research.getByText("Verwendet für Markt- und Konkurrenzvergleich.")
    ).toBeVisible()
    // Die öffentliche Evaluationsquelle liegt in der Recherche-Gruppe …
    await expect(
      research.getByText("Öffentliche Marktquelle (Demo)").first()
    ).toBeVisible()
    // … und NIE in der Antragsgruppe; die Projektunterlagen ebenso wenig.
    await expect(
      primary.getByText("Öffentliche Marktquelle (Demo)")
    ).toHaveCount(0)
    await expect(primary.getByText("Demo A - Arbeitsplan.txt")).toHaveCount(0)
    await expect(
      documents.getByText("Demo A - Arbeitsplan.txt").first()
    ).toBeVisible()
  })

  test("B5: Belegstufen sichtbar (gefunden + stark gestützt) und erklärt", async ({ page }) => {
    test.setTimeout(180_000)
    await login(page)
    await openProject(page, /Verbundwerkstoffe \(Demo\)/)
    await page.goto("/anforderungen?tab=evidenz")
    await expect(
      page.getByText(/Textstelle gefunden/).first()
    ).toBeVisible({ timeout: 20_000 })
    await expect(page.getByText("Stark gestützt").first()).toBeVisible()
    const defs = page.getByText("Was bedeuten die Belegstufen?")
    await expect(defs).toBeVisible()
    await defs.click()
    await expect(
      page.getByText(
        "Die Passage ist in der Quelle auffindbar; die fachliche Stützung ist noch offen."
      )
    ).toBeVisible()
    test.info().annotations.push({
      type: "limitation",
      description:
        "«Teilweise gestützt» und «Widersprüchlich/unklar» sind deterministisch nicht als Datenzustand erreichbar (kein Anker-Verwerfen-Control in der UI); die Stufen sind über die Definitionen + Unit-Tests (lib/evidence-ladder) abgedeckt.",
    })
  })

  test("B7: Marktvergleich ready aus dem Seed — belegte Zeile, keine Erfindungen", async ({ page }) => {
    test.setTimeout(180_000)
    await login(page)
    await openProject(page, /Verbundwerkstoffe \(Demo\)/)
    await page.goto("/quellen")
    const section = page.getByTestId("market-comparison-section")
    await section.scrollIntoViewIfNeeded()
    await expect(section).toBeVisible({ timeout: 20_000 })
    await expect(page.getByTestId("market-comparison-table")).toBeVisible()
    await expect(
      page.getByText("Referenzlösung Alpha (Demo)").first()
    ).toBeVisible()
    await expect(page.getByText(/Fundstelle: exakt gefunden/).first()).toBeVisible()
    // Höchstens fünf Konsequenzen, falls vorhanden (Cap zusätzlich im
    // Backend-Executor [:5] und in test/market-comparison-section.test.tsx).
    const consequences = page.getByTestId("market-consequences")
    if (await consequences.isVisible().catch(() => false)) {
      expect(await consequences.locator("li").count()).toBeLessThanOrEqual(5)
    } else {
      test.info().annotations.push({
        type: "note",
        description:
          "Seed-Vergleich ohne Konsequenzenliste — Cap (≤5) ist durch Unit-Test und Backend-Slice [:5] belegt.",
      })
    }
    await shot(page, "markt-ready-tabelle")
  })

  test("B9: Qualitätsübersicht mit vier Kategorien; not_run nie als Zahl", async ({ page }) => {
    test.setTimeout(180_000)
    await login(page)
    await openProject(page, /Verbundwerkstoffe \(Demo\)/)
    await page.goto("/review")
    await expect(
      page.getByRole("heading", { name: "Qualitätsprüfung", exact: true })
    ).toBeVisible({ timeout: 20_000 })
    for (const label of [
      "Formale Blocker",
      "Fehlende Pflichtangaben",
      "Wichtige Qualitätsrisiken",
      "Offene menschliche Prüfungen",
    ]) {
      await expect(page.getByText(label, { exact: true }).first()).toBeVisible()
    }
    await shot(page, "qualitaetsuebersicht")

    // Projekt B (ohne Qualitätslauf): nicht Geprüftes heisst «Nicht geprüft»,
    // erscheint nie als 0.
    await openProject(page, /Produktionsanlagen \(Demo\)/)
    await page.goto("/review")
    await expect(
      page.getByRole("heading", { name: "Qualitätsprüfung", exact: true })
    ).toBeVisible({ timeout: 20_000 })
    await expect(page.getByText("Nicht geprüft").first()).toBeVisible()
  })

  test("Phase C: Beleg-Details eines gespeicherten Vorschlags über den echten Read-Pfad", async ({ page }) => {
    test.setTimeout(240_000)
    await login(page)
    await openProject(page, /Verbundwerkstoffe \(Demo\)/)
    await page.goto("/editor?field=INTRO.APP.EXECUTIVE_SUMMARY")
    // Gespeicherter Vorschlag aus dem Lauf (Seed) wird zum Prüfen angeboten.
    await expect(page.getByTestId("run-suggestion-hint")).toBeVisible({
      timeout: 30_000,
    })
    await page.getByRole("button", { name: "Vorschlag prüfen" }).click()
    const dialog = page.getByRole("dialog")
    await expect(dialog).toBeVisible()
    // Ehrliche Herkunft: Demo-Kennzeichnung, nie Live-KI.
    await expect(dialog.getByText("Demo", { exact: true }).first()).toBeVisible()
    await expect(dialog.getByText("Live-KI")).toHaveCount(0)

    // Hartes Produktgate: Anzahl + pro Beleg Quelle, Fundstelle, Ausschnitt,
    // Supportstatus — echte EvidenceAnchor-Daten, kein Fixture.
    const usage = dialog.getByTestId("evidence-usage")
    await expect(usage).toBeVisible()
    await expect(
      usage.getByText("Dieser Vorschlag verwendet 1 geprüften Beleg.")
    ).toBeVisible()
    await usage.getByText("Belegdetails anzeigen").click()
    const item = usage.locator("li").first()
    await expect(item).toBeVisible()
    await expect(item.getByText(/Demo A - /)).toBeVisible()
    await expect(item.getByText("Fundstelle bestätigt")).toBeVisible()
    await expect(item.getByText(/Abschnitt /)).toBeVisible()
    const quote = await item.locator("p").last().textContent()
    expect((quote ?? "").trim().length).toBeGreaterThan(20)
    await shot(page, "beleg-details-gespeicherter-vorschlag")
  })

  test("Phase D: Export-Ansicht (visuelle Evidenz)", async ({ page }) => {
    test.skip(
      process.env.FINAL_VISUAL !== "1",
      "Set FINAL_VISUAL=1 to capture the final visual evidence screenshots."
    )
    test.setTimeout(180_000)
    await login(page)
    await openProject(page, /Verbundwerkstoffe \(Demo\)/)
    await page.goto("/export")
    await expect(
      page.getByRole("heading", { name: /Innolink-Übernahme/ })
    ).toBeVisible({ timeout: 20_000 })
    await shot(page, "export-center")
  })
})
