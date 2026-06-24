import { test, expect } from "@playwright/test"

// Live smoke: login → create project → create text source → processed →
// reload → still visible → logout. Requires the backend + frontend (live)
// running. Uses the seeded dev lead-admin.
const EMAIL = process.env.E2E_EMAIL ?? "anna.keller@example.test"
const PASSWORD = process.env.E2E_PASSWORD ?? "changeme-dev-lead"

test("source ingestion live smoke", async ({ page }) => {
  // 1. Login
  await page.goto("/login")
  await page.getByLabel("E-Mail").fill(EMAIL)
  await page.getByLabel("Passwort").fill(PASSWORD)
  await page.getByRole("button", { name: "Anmelden" }).click()
  await expect(page).toHaveURL(/\/$/, { timeout: 20_000 })

  // 2. Create a project via Intake
  await page.goto("/intake")
  await page.getByLabel(/Antragstitel/).fill("E2E Source Project")
  await page.getByLabel(/Projektidee/).fill("Eine Test-Projektidee für E2E.")
  await page.getByText("Öffentlich", { exact: true }).click()
  await page.getByRole("button", { name: "Antrag anlegen" }).click()
  await expect(page).toHaveURL(/\/quellen/, { timeout: 20_000 })

  // 3. Add a text source
  await page.getByRole("button", { name: "Text als Quelle hinzufügen" }).click()
  await page.getByLabel("Name").fill("E2E Notiz")
  await page
    .getByLabel("Text")
    .fill("Dies ist der Inhalt der E2E-Textquelle für die Verarbeitung.")
  await page.getByRole("button", { name: "Hinzufügen" }).click()

  // 4. The source appears and becomes processed
  await expect(page.getByText("E2E Notiz")).toBeVisible({ timeout: 20_000 })
  await expect(page.getByText("Verarbeitet").first()).toBeVisible({
    timeout: 20_000,
  })

  // 5. Refresh — the source persists
  await page.reload()
  await expect(page.getByText("E2E Notiz")).toBeVisible({ timeout: 20_000 })

  // 6. Logout
  await page.getByText("Anna Keller").first().click()
  await page.getByText("Abmelden").click()
  await expect(page).toHaveURL(/\/login/, { timeout: 20_000 })
})

// Unicode regression (Milestone 4.1): German umlauts/quotes must ingest to
// `processed` and render correctly after a refresh (byte → DB → BFF → UI).
const UMLAUT_NAME = "Prüfung Förderfähigkeit – Müller & Söhne"

test("umlaut text source ingests and displays after refresh", async ({ page }) => {
  await page.goto("/login")
  await page.getByLabel("E-Mail").fill(EMAIL)
  await page.getByLabel("Passwort").fill(PASSWORD)
  await page.getByRole("button", { name: "Anmelden" }).click()
  await expect(page).toHaveURL(/\/$/, { timeout: 20_000 })

  await page.goto("/intake")
  await page.getByLabel(/Antragstitel/).fill("E2E Unicode Projekt")
  await page.getByLabel(/Projektidee/).fill("Projektidee mit Umlauten: äöüß.")
  await page.getByText("Öffentlich", { exact: true }).click()
  await page.getByRole("button", { name: "Antrag anlegen" }).click()
  await expect(page).toHaveURL(/\/quellen/, { timeout: 20_000 })

  await page.getByRole("button", { name: "Text als Quelle hinzufügen" }).click()
  await page.getByLabel("Name").fill(UMLAUT_NAME)
  await page
    .getByLabel("Text")
    .fill("Müller & Söhne prüfen die Förderfähigkeit für größere Vorhaben. äöüÄÖÜß")
  await page.getByRole("button", { name: "Hinzufügen" }).click()

  // Previously this source ended up `failed`; it must now become processed.
  await expect(page.getByText(UMLAUT_NAME)).toBeVisible({ timeout: 20_000 })
  await expect(page.getByText("Verarbeitet").first()).toBeVisible({
    timeout: 20_000,
  })

  // Refresh — the umlaut name persists and renders correctly.
  await page.reload()
  await expect(page.getByText(UMLAUT_NAME)).toBeVisible({ timeout: 20_000 })

  await page.getByText("Anna Keller").first().click()
  await page.getByText("Abmelden").click()
  await expect(page).toHaveURL(/\/login/, { timeout: 20_000 })
})
