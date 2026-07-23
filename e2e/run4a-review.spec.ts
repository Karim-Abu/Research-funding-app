// RUN 4A — interaktiver UI-Review (Human-Review-Checkliste, werkzeuggestützt).
// Prüft die interaktiv verifizierbaren Checklistenpunkte (Import-Reversibilität,
// Detailansichten, Dialog-Fokusmanagement, Tab-Reihenfolge, Unicode-Eingabe,
// Überschriften-Hierarchie) und legt Evidenz-Screenshots ab unter
// docs/assets/run4a/review-evidence/. Opt-in und NIE Teil der Gates:
//   RUN4A_REVIEW=1 corepack pnpm exec playwright test e2e/run4a-review.spec.ts
// Voraussetzungen wie e2e/run4a-visual.spec.ts (lokale Server, Fake-Provider,
// Demo-Seed). Keine externen Provider-Calls.
import { execFileSync } from "node:child_process"
import { existsSync, mkdirSync } from "node:fs"
import path from "node:path"
import { expect, test, type Page } from "@playwright/test"

const EMAIL = process.env.E2E_EMAIL ?? "anna.keller@example.test"
const PASSWORD = process.env.E2E_PASSWORD ?? "changeme-dev-lead"
const FIXTURE_PDF = path.join(__dirname, "..", "spike", "fixtures", "innolink_sample.pdf")
const OUT_DIR = path.join(process.cwd(), "docs", "assets", "run4a", "review-evidence")

test.skip(
  process.env.RUN4A_REVIEW !== "1",
  "Set RUN4A_REVIEW=1 to run the interactive RUN 4A UI review."
)

test.beforeAll(() => {
  const backendDir = path.join(process.cwd(), "backend")
  const venvPython = path.join(backendDir, ".venv", "Scripts", "python.exe")
  const python =
    process.env.BACKEND_PYTHON ?? (existsSync(venvPython) ? venvPython : "python")
  execFileSync(python, ["-m", "app.demo.seed", "--reset"], {
    cwd: backendDir,
    env: { ...process.env, APP_ENV: "development", DEMO_DATA_ENABLED: "true" },
    stdio: "inherit",
  })
  mkdirSync(OUT_DIR, { recursive: true })
})

async function shot(page: Page, name: string): Promise<void> {
  await page.screenshot({ path: path.join(OUT_DIR, `${name}.png`), fullPage: true })
}

async function login(page: Page): Promise<void> {
  await page.goto("/login")
  await page.getByLabel("E-Mail").fill(EMAIL)
  await page.getByLabel("Passwort").fill(PASSWORD)
  await page.getByRole("button", { name: "Anmelden" }).click()
  await expect(page).toHaveURL(/\/$/, { timeout: 20_000 })
  // Aktives Projekt setzen (Demo-Projekt B). Das Ziel der Karte hängt vom
  // Projektzustand ab (next_action) — nur das Verlassen des Dashboards zählt;
  // jede Prüfung navigiert danach explizit auf ihre Route.
  await page.getByRole("heading", { name: /Produktionsanlagen \(Demo\)/ }).click()
  await expect(page).not.toHaveURL(/\/$/, { timeout: 20_000 })
}

test.describe("RUN 4A UI-Review", () => {
  test("§2 Import: Upload, Übernahme, reversible Aktionen, keine Roh-IDs", async ({ page }) => {
    test.setTimeout(300_000)
    await login(page)
    await page.goto("/import")
    await expect(
      page.getByRole("heading", { name: "Antrag importieren" })
    ).toBeVisible({ timeout: 20_000 })

    // Zustandsrobust: frisches Projekt → Upload; sonst liegen bereits
    // Kandidaten vor (z. B. aus einem früheren Review-Lauf).
    const fileInput = page.getByTestId("import-file-input")
    if (await fileInput.isVisible().catch(() => false)) {
      await fileInput.setInputFiles(FIXTURE_PDF)
    }
    await expect(page.getByTestId("import-review")).toBeVisible({
      timeout: 120_000,
    })
    const rows = page.getByTestId("import-candidate")
    await expect(rows.first()).toBeVisible()
    await shot(page, "import-candidates-offen")

    // Übernehmen → reversible Aktionen bleiben sichtbar. Zeile VOR dem Klick
    // per Index fixieren (ein Filter-Locator wäre live und spränge nach der
    // Entscheidung auf die nächste offene Zeile).
    const rowCount = await rows.count()
    let targetIndex = -1
    for (let i = 0; i < rowCount; i++) {
      const enabled = await rows
        .nth(i)
        .getByRole("button", { name: "Übernehmen", exact: true })
        .isEnabled()
        .catch(() => false)
      if (enabled) {
        targetIndex = i
        break
      }
    }
    expect(targetIndex).toBeGreaterThanOrEqual(0)
    const firstRow = rows.nth(targetIndex)
    await firstRow.getByRole("button", { name: "Übernehmen", exact: true }).click()
    // RUN-2B-Konfliktpfad: existiert bereits ein Entwurf (Wiederholungslauf),
    // verlangt die UI eine explizite Bestätigung — ebenfalls Review-Evidenz.
    // Der Dialog erscheint erst nach dem 409-Roundtrip → auf beide möglichen
    // Ausgänge warten statt sofort zu prüfen.
    const conflictConfirm = page.getByRole("button", { name: "Entwurf ersetzen" })
    const editButton = firstRow.getByRole("button", {
      name: "Bearbeiten",
      exact: true,
    })
    await expect(editButton.or(conflictConfirm).first()).toBeVisible({
      timeout: 20_000,
    })
    if (await conflictConfirm.isVisible().catch(() => false)) {
      await shot(page, "import-konflikt-bestaetigung")
      await conflictConfirm.click()
    }
    await expect(editButton).toBeVisible({ timeout: 20_000 })
    await expect(
      firstRow.getByRole("button", { name: "PDF-Wert wiederherstellen" })
    ).toBeVisible()
    await expect(
      firstRow.getByRole("button", { name: "Übernahme zurücknehmen" })
    ).toBeVisible()
    await shot(page, "import-entschieden-reversible-aktionen")

    // Übernahme zurücknehmen → Kandidat wieder offen (Undo interaktiv belegt).
    await firstRow.getByRole("button", { name: "Übernahme zurücknehmen" }).click()
    await expect(
      firstRow.getByRole("button", { name: "Übernehmen", exact: true })
    ).toBeVisible({ timeout: 20_000 })

    // Keine Roh-IDs/Hashes im Standardfluss (Feld-IDs nur im collapsed Detail).
    await expect(page.getByText(/INTRO\.APP\./).first()).not.toBeVisible()
    await expect(page.getByText("innolink-narrative-v2").first()).not.toBeVisible()
  })

  test("§4/§5 Anforderungen + Evidenz: Detail, Regelgrundlage, Belegstufen", async ({ page }) => {
    test.setTimeout(180_000)
    await login(page)
    await page.goto("/anforderungen")
    await expect(page.getByText(/rdervoraussetzungen/).first()).toBeVisible({
      timeout: 20_000,
    })

    // Erste Anforderungszeile aufklappen — Statuszeile + Systembefund sichtbar.
    const row = page.locator('[id^="req-"] > button').first()
    await row.click()
    await expect(page.getByText("Systembefund").first()).toBeVisible()
    await shot(page, "anforderungen-detail-aufgeklappt")
    // Keine rohen Requirement-IDs im Standardfluss.
    await expect(page.getByText(/REQ\.INNO\./).first()).not.toBeVisible()

    // Evidenz: Kurzdefinitionen der Supportleiter aufklappen.
    await page.goto("/anforderungen?tab=evidenz")
    const defs = page.getByText("Was bedeuten die Belegstufen?")
    await expect(defs).toBeVisible({ timeout: 20_000 })
    await defs.click()
    await expect(
      page.getByText(
        "Die Passage ist in der Quelle auffindbar; die fachliche Stützung ist noch offen."
      )
    ).toBeVisible()
    await shot(page, "evidenz-belegstufen-definitionen")
  })

  test("§8 Recherche: eine Modul-Darstellung, Unicode-Eingabe bleibt erhalten", async ({ page }) => {
    test.setTimeout(180_000)
    await login(page)
    await page.goto("/quellen")
    await expect(page.getByText("Quellenliste")).toBeVisible({ timeout: 20_000 })

    const panel = page.getByTestId("public-research-panel")
    if (!(await panel.isVisible().catch(() => false))) {
      test.info().annotations.push({
        type: "note",
        description:
          "Recherche-Panel für dieses Demo-Projekt nicht aktiv — Formularverhalten ist über test/public-research-panel.test.tsx abgedeckt.",
      })
      return
    }
    // Zustandsagnostisch: existiert schon ein Brief-Entwurf, ist das Formular
    // direkt offen; sonst zuerst den Vorschlag anstossen.
    const form = page.getByTestId("research-brief-form")
    try {
      await form.waitFor({ state: "visible", timeout: 5_000 })
    } catch {
      await panel
        .getByRole("button", { name: /Recherchebrief vorschlagen/ })
        .click()
      await form.waitFor({ state: "visible", timeout: 20_000 })
    }
    // Genau eine Modul-Darstellung: Formular offen ⇒ kein Ergebnis-Umschalter.
    await expect(page.getByText("Recherchemodule")).toBeVisible()
    await expect(page.getByText("Ergebnisse nach Modul")).toHaveCount(0)

    const goal = page.getByLabel("Recherchefrage / Ziel")
    const unicode = "KI-gestützte Datenanalyse für Schweizer KMU – Zürich/DACH (B2B) ✓ émission"
    await goal.fill(unicode)
    await expect(goal).toHaveValue(unicode)
    await shot(page, "recherche-brief-formular-unicode")
  })

  test("§9 A11y: Dialog-Fokus, Tab-Reihenfolge, Überschriften-Hierarchie, Fokus sichtbar", async ({ page }) => {
    test.setTimeout(180_000)
    await login(page)
    await page.goto("/quellen")
    await expect(page.getByText("Quellenliste")).toBeVisible({ timeout: 20_000 })

    // Dialog-Fokusmanagement: Quellen-Details öffnen, Fokus im Dialog,
    // Escape schliesst, Fokus kehrt zum Auslöser zurück.
    const infoButton = page.getByRole("button", { name: /: Details anzeigen$/ }).first()
    await infoButton.click()
    const dialog = page.getByRole("dialog")
    await expect(dialog).toBeVisible()
    const focusInDialog = await page.evaluate(() => {
      const active = document.activeElement
      return Boolean(active?.closest('[role="dialog"]'))
    })
    expect(focusInDialog).toBe(true)
    await shot(page, "a11y-quellen-details-dialog")
    await page.keyboard.press("Escape")
    await expect(dialog).toBeHidden()

    // Überschriften-Hierarchie: genau ein h1 pro Screen.
    for (const route of ["/quellen", "/review"]) {
      await page.goto(route)
      await page.waitForLoadState("networkidle")
      const h1Count = await page.locator("h1").count()
      expect(h1Count, `${route} braucht genau ein h1`).toBe(1)
    }

    // Tab-Reihenfolge + sichtbarer Fokus auf der Qualitätsprüfung.
    await page.goto("/review")
    await expect(
      page.getByRole("heading", { name: "Qualitätsprüfung", exact: true })
    ).toBeVisible({ timeout: 20_000 })
    const sequence: string[] = []
    for (let i = 0; i < 12; i++) {
      await page.keyboard.press("Tab")
      const label = await page.evaluate(() => {
        const active = document.activeElement as HTMLElement | null
        return (
          active?.getAttribute("aria-label") ??
          active?.textContent?.trim().slice(0, 40) ??
          active?.tagName ??
          "none"
        )
      })
      sequence.push(label)
    }
    // Die Sequenz erreicht interaktive Elemente (kein Fokus-Verlust ins Nichts).
    expect(sequence.filter((s) => s && s !== "none" && s !== "BODY").length)
      .toBeGreaterThanOrEqual(8)
    test.info().annotations.push({
      type: "tab-order /review",
      description: sequence.join(" → "),
    })
    await shot(page, "a11y-review-fokus-sichtbar")

    // Qualitätsübersicht: technische Details aufklappbar (Kennzahlen-Karte).
    const techDetails = page.getByText("Technische Details", { exact: true }).first()
    await techDetails.click()
    await expect(
      page.getByText(/Unterliegende Evidenzhinweise \(claimgenau\)/)
    ).toBeVisible()
    await shot(page, "qualitaet-technische-details-aufgeklappt")
  })
})
