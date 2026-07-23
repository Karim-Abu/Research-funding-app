// RUN 4A — visuelle Nachweise (Leitplanke 11): Screenshots der zentralen
// Screens bei 1440×900, 1280×800 und 768×1024 nach docs/assets/run4a/.
// Opt-in und NIE Teil der Gates:
//   RUN4A_VISUAL=1 corepack pnpm exec playwright test e2e/run4a-visual.spec.ts
// Voraussetzungen wie beim Demo-Dataset-Spec: Backend (uvicorn :8000, Fake-
// Provider, DEMO_DATA_ENABLED=true) und Frontend (APP_BACKEND_MODE=live :3000)
// laufen lokal; der Seed erzeugt zwei synthetische Demo-Projekte. Es finden
// keine externen Provider-Calls statt.
import { execFileSync } from "node:child_process"
import { existsSync, mkdirSync } from "node:fs"
import path from "node:path"
import { expect, test, type Page } from "@playwright/test"

const EMAIL = process.env.E2E_EMAIL ?? "anna.keller@example.test"
const PASSWORD = process.env.E2E_PASSWORD ?? "changeme-dev-lead"

test.skip(
  process.env.RUN4A_VISUAL !== "1",
  "Set RUN4A_VISUAL=1 to capture the RUN 4A visual evidence screenshots."
)

const OUT_DIR = path.join(process.cwd(), "docs", "assets", "run4a")
const VIEWPORTS = [
  { width: 1440, height: 900 },
  { width: 1280, height: 800 },
  { width: 768, height: 1024 },
]

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

async function shoot(page: Page, name: string): Promise<void> {
  for (const viewport of VIEWPORTS) {
    await page.setViewportSize(viewport)
    // Layout-Reflow abwarten (responsive Umbrüche, Sticky-Footer).
    await page.waitForTimeout(400)
    await page.screenshot({
      path: path.join(OUT_DIR, `${name}-${viewport.width}x${viewport.height}.png`),
      fullPage: true,
    })
  }
}

test("RUN 4A — Screenshots der zentralen Screens und Zustände", async ({ page }) => {
  test.setTimeout(300_000)
  await page.goto("/login")
  await page.getByLabel("E-Mail").fill(EMAIL)
  await page.getByLabel("Passwort").fill(PASSWORD)
  await page.getByRole("button", { name: "Anmelden" }).click()
  await expect(page).toHaveURL(/\/$/, { timeout: 20_000 })
  await expect(page.getByText(/Produktionsanlagen \(Demo\)/)).toBeVisible({
    timeout: 20_000,
  })
  await shoot(page, "dashboard")

  // Anforderungen (Projekt mit offenen Anforderungen/Blockern).
  await page.getByRole("heading", { name: /Produktionsanlagen \(Demo\)/ }).click()
  await expect(page).toHaveURL(/\/anforderungen/, { timeout: 20_000 })
  await expect(page.getByText(/rdervoraussetzungen/).first()).toBeVisible({
    timeout: 20_000,
  })
  await shoot(page, "anforderungen")

  // Evidenz (Supportleiter + Kurzdefinitionen).
  await page.goto("/anforderungen?tab=evidenz")
  await expect(
    page.getByText("Was bedeuten die Belegstufen?").or(page.getByText(/Beleg/)).first()
  ).toBeVisible({ timeout: 20_000 })
  await shoot(page, "evidenz")

  // Quellen (Zweck-Gruppierung, Recherche-Panel, Marktvergleich).
  await page.goto("/quellen")
  await expect(page.getByText("Quellenliste")).toBeVisible({ timeout: 20_000 })
  await shoot(page, "quellen")

  // Antrag importieren (ruhige Kopfstruktur).
  await page.goto("/import")
  await expect(
    page.getByRole("heading", { name: "Antrag importieren" })
  ).toBeVisible({ timeout: 20_000 })
  await shoot(page, "import")

  // Qualitätsprüfung (vier Kennzahlen, Aufgabenliste).
  await page.goto("/review")
  await expect(
    page.getByRole("heading", { name: "Qualitätsprüfung" })
  ).toBeVisible({ timeout: 20_000 })
  await shoot(page, "review")
})
