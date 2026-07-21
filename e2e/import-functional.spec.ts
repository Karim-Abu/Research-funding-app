import { test, expect } from "@playwright/test"
import path from "node:path"
import { choosePublic, getActiveProjectId, login, logout } from "./helpers"

// FUNKTIONALER IMPORT-E2E (Ebene B — Structured import, CI-pflichtig):
// Beweist fachlich, dass ein unfertiger Antrag im ÄLTEREN Innolink-Schema
// korrekt ausgelesen wird: leere Executive Summary bleibt leer, Titel/Dauer/
// Partner/Budget/Antworten erscheinen als strukturierte Kandidaten mit exakten
// Werten, die Alt→Neu-Migration (IPR → 4.5.x, alt-4.5 → 4.6) ist sichtbar, und
// Partner + Budget landen NACH menschlicher Bestätigung OHNE manuelle
// Neuanlage in den Formularen. Nichts wird automatisch übernommen (HITL).
//
// Fixture: spike/fixtures/innolink_structured.pdf — rein synthetisches Projekt
// «TERRAFLUX» (spike/make_fixture.py; Testdaten-Policy R0.4). Deterministisch,
// keine Provider nötig; gleiche Server-Umgebung wie der technische E2E.

const STRUCTURED_PDF = path.join(
  __dirname,
  "..",
  "spike",
  "fixtures",
  "innolink_structured.pdf"
)

const TITLE_DE = "TERRAFLUX - Adaptive Bewässerungssteuerung für Stadtgrün"
const PARTNERS: ReadonlyArray<readonly [string, string]> = [
  ["Nordlicht Institut für Angewandte Forschung", "research_partner"],
  ["Voltaris AG", "implementation_partner"],
  ["Brimatec GmbH", "implementation_partner"],
]
const BUDGET = {
  direct_total_project_costs_excluding_overhead: 200000,
  implementation_own_contribution: 105000,
  cash_contribution: 13000,
  total_requested_funding: 82000,
  total_requested_funding_including_overhead: 94300,
} as const

test("Funktionaler Import: Altstruktur-PDF wird korrekt ausgelesen, Partner und Budget ohne Neuanlage", async ({
  page,
}) => {
  test.setTimeout(300_000)
  const intakeTitle = `Funktionaler Import ${Date.now()}`

  await test.step("1. Login", async () => {
    await login(page)
  })

  await test.step("2. Projekt anlegen und Altstruktur-PDF hochladen", async () => {
    await page.goto("/intake")
    await page.getByLabel(/Projekttitel/).fill(intakeTitle)
    await page
      .getByRole("textbox", { name: /Projektidee/ })
      .fill("Synthetisches Testprojekt für den funktionalen Import-Pfad.")
    await page.getByTestId("intake-file-input").setInputFiles(STRUCTURED_PDF)
    await choosePublic(page)
    await page.getByRole("button", { name: "Projekt erstellen und weiter" }).click()
    await expect(page).toHaveURL(/\/import\?source=/, { timeout: 20_000 })
    await expect(page.getByTestId("import-review")).toBeVisible({ timeout: 60_000 })
  })

  const projectId = await getActiveProjectId(page)

  await test.step("3. Narrative Kandidaten: leere Executive Summary bleibt leer", async () => {
    await expect(page.getByTestId("import-candidate")).toHaveCount(8)
    // HITL: nichts ist vorentschieden.
    await expect(page.getByText("Übernommen", { exact: true })).toHaveCount(0)

    const summaryRow = page
      .getByTestId("import-candidate")
      .filter({ hasText: "Executive Summary (wird nicht publiziert)" })
    await expect(summaryRow.getByText("Leer", { exact: true })).toBeVisible()
    // Ein leerer Kandidat ist nicht übernehmbar — er erbt nie Folgeinhalte.
    await expect(
      summaryRow.getByRole("button", { name: "Übernehmen", exact: true })
    ).toBeDisabled()

    const abstractRow = page
      .getByTestId("import-candidate")
      .filter({ hasText: "Abstract (wird in Aramis publiziert)" })
    await expect(
      abstractRow.getByText("Inhalt erkannt", { exact: true })
    ).toBeVisible()
  })

  await test.step("4. Alt→Neu-Migration ist ausgewiesen (IPR → 4.5.x, alt-4.5 → 4.6)", async () => {
    const solutionRow = page
      .getByTestId("import-candidate")
      .filter({ hasText: "Innovation & Lösung" })
    await expect(
      solutionRow.getByText("Altstruktur migriert", { exact: true }).first()
    ).toBeVisible()
    await solutionRow.getByRole("button", { name: /Abschnittsdetails/ }).click()
    const sections = solutionRow.getByTestId("import-section-metadata")
    await expect(
      sections.filter({ hasText: "Zielabschnitt: 4.5.1" })
    ).toHaveCount(1)
    await expect(
      sections.filter({ hasText: "Zielabschnitt: 4.5.2 / 4.5.3" })
    ).toHaveCount(1)
    await expect(
      sections.filter({ hasText: "Zielabschnitt: 4.6" })
    ).toHaveCount(1)
    await expect(
      sections
        .filter({ hasText: "Aus älterer Innolink-Struktur migriert" })
        .first()
    ).toBeVisible()
    // Mehrdeutige Altangabe (4.5.2/4.5.3) verlangt fachliche Zuordnung.
    await expect(
      sections.filter({ hasText: /Altangabe kann 4\.5\.2 oder 4\.5\.3/ })
    ).toHaveCount(1)
  })

  await test.step("5. 0 Management-Stunden erzeugen einen Erklärungs-Vorschlag", async () => {
    const managementRow = page
      .getByTestId("import-candidate")
      .filter({ hasText: "Erläuterung zur Verteilung der Management-Stunden" })
    await managementRow.getByRole("button", { name: /Abschnittsdetails/ }).click()
    await expect(
      managementRow.getByText(
        "No project-management hours are planned (0 of 4000 hours)."
      )
    ).toBeVisible()
  })

  await test.step("6. Strukturierte Kandidaten mit exakten Werten", async () => {
    const rows = page.getByTestId("structured-import-candidate")
    await expect(rows).toHaveCount(15)

    await expect(
      rows.filter({ hasText: "Projekttitel" }).filter({ hasText: TITLE_DE })
    ).toHaveCount(1)
    await expect(
      rows.filter({ hasText: "Projektdauer" }).filter({ hasText: "18" })
    ).toHaveCount(1)
    await expect(
      rows
        .filter({ hasText: "Direkte Projektkosten ohne Overhead" })
        .filter({ hasText: "200000" })
    ).toHaveCount(1)
    await expect(
      rows
        .filter({ hasText: "Eigenleistung Umsetzungspartner" })
        .filter({ hasText: "105000" })
    ).toHaveCount(1)
    await expect(
      rows.filter({ hasText: "Barbeitrag" }).filter({ hasText: "13000" })
    ).toHaveCount(1)
    for (const [name] of PARTNERS) {
      await expect(rows.filter({ hasText: name })).toHaveCount(1)
    }
    await expect(
      rows.filter({ hasText: "Wissenschaftliche Integrität" })
    ).toHaveCount(1)
    await expect(
      rows.filter({ hasText: "Management-Stunden" })
    ).toHaveCount(1)
  })

  await test.step("7. Alle strukturierten Kandidaten menschlich bestätigen", async () => {
    const rows = page.getByTestId("structured-import-candidate")
    const decidedPattern = /Übernommen – menschlich bestätigt|Bearbeitet übernommen/
    for (let index = 0; index < 15; index++) {
      const row = rows.nth(index)
      const accept = row.getByRole("button", { name: "Übernehmen", exact: true })
      // Die PDF-Dauer bleibt sichtbar, ist aber nur Vergleichswert. Start und
      // Ende werden übernommen; die Dauer wird daraus zentral abgeleitet.
      if ((await accept.count()) === 0) continue
      await accept.click()
      const decided = row.getByText(decidedPattern)
      const confirm = page.getByTestId("structured-import-confirm-overwrite")
      // Konflikt (z. B. Projekttitel aus dem Intake) verlangt ausdrückliche
      // Bestätigung — nichts wird still überschrieben.
      await expect(decided.or(confirm)).toBeVisible({ timeout: 20_000 })
      if (await confirm.isVisible().catch(() => false)) {
        await confirm.click()
      }
      await expect(decided).toBeVisible({ timeout: 20_000 })
    }
  })

  await test.step("8. Partner erscheinen ohne manuelle Neuanlage", async () => {
    await page.goto("/partner")
    const summary = page.getByTestId("structured-import-summary")
    await expect(summary).toBeVisible({ timeout: 20_000 })
    await expect(summary).toContainText("3 Partner")
    await expect(summary).toContainText("5 Budgetangaben")

    for (const [name] of PARTNERS) {
      await expect(page.getByText(name).first()).toBeVisible()
    }
    // Nur die Partnerliste zählen (das Anlage-Formular enthält die Typen
    // ebenfalls als Auswahl-Optionen).
    await expect(
      page.getByRole("listitem").getByText("Forschungspartner", { exact: true })
    ).toHaveCount(1)
    await expect(
      page.getByRole("listitem").getByText("Umsetzungspartner", { exact: true })
    ).toHaveCount(2)
    // Herkunft ist ausgewiesen: aus dem PDF übernommen, menschlich bestätigt.
    await expect(
      page
        .getByTestId("import-provenance")
        .filter({ hasText: "Aus PDF übernommen" })
    ).toHaveCount(3)
  })

  await test.step("9. Budgetformular ist aus dem PDF vorbefüllt, Precheck konsistent", async () => {
    await expect(
      page.getByLabel("Direkte Projektkosten (ohne Overhead)")
    ).toHaveValue("200000", { timeout: 20_000 })
    await expect(page.getByLabel("Eigenleistung Umsetzungspartner")).toHaveValue(
      "105000"
    )
    await expect(page.getByLabel("Barbeitrag (Cash)")).toHaveValue("13000")
    await expect(page.getByText("18 Monate", { exact: true })).toBeVisible()
    // Regel-Precheck über den Live-Daten: Umsetzungsbeitrag (own+cash) 59 %
    // und Barbeitrag 6.5 % → beide formal erfüllt.
    const precheck = page.getByTestId("budget-precheck")
    await expect(precheck.getByText("Erfüllt", { exact: true })).toHaveCount(2, {
      timeout: 20_000,
    })
  })

  await test.step("10. Persistierte Werte exakt prüfen (API)", async () => {
    const project = (await (
      await page.request.get(`/api/projects/${projectId}`)
    ).json()) as Record<string, unknown>
    expect(project.title).toBe(TITLE_DE)
    expect(project.duration_months).toBe(18)
    for (const [field, amount] of Object.entries(BUDGET)) {
      expect(project[field], field).toBe(amount)
    }

    const partners = (await (
      await page.request.get(`/api/projects/${projectId}/partners`)
    ).json()) as Array<{ name: string; partner_type: string; country: string }>
    expect(partners).toHaveLength(3)
    for (const [name, partnerType] of PARTNERS) {
      const found = partners.find((p) => p.name === name)
      expect(found, name).toBeTruthy()
      expect(found!.partner_type).toBe(partnerType)
      expect(found!.country).toBe("CH")
    }
  })

  await test.step("11. Abmelden", async () => {
    await logout(page)
  })
})
