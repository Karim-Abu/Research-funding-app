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
  await page.getByRole("textbox", { name: /Projektidee/ }).fill("Eine Test-Projektidee für E2E.")
  await page.getByText("Öffentlich", { exact: true }).click()
  await page.getByRole("button", { name: "Antrag anlegen" }).click()
  await expect(page).toHaveURL(/\/quellen/, { timeout: 20_000 })

  // 3. Add a text source
  await page.getByRole("button", { name: "Text einfügen" }).click()
  await page.getByLabel("Titel der Quelle").fill("E2E Notiz")
  await page
    .getByLabel("Textinhalt")
    .fill("Dies ist der Inhalt der E2E-Textquelle für die Verarbeitung.")
  await page.getByRole("button", { name: "Als Quelle hinzufügen" }).click()

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

// Upload smoke (Slice 0 / T1): the file upload posts to the dedicated
// /api/projects/{id}/sources/files route (previously 404 in live mode).
// A small synthetic PDF must appear as a source and become "Verarbeitet".
// Local run: pnpm exec playwright test e2e/source-ingestion.spec.ts
// (requires uvicorn :8000 + APP_BACKEND_MODE=live pnpm dev :3000).

// Minimal valid single-page PDF with extractable Helvetica text (ASCII only).
function minimalPdf(text: string): Buffer {
  const objects = [
    "1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
    "2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
    "3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] " +
      "/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>\nendobj\n",
    "4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
  ]
  const stream = `BT /F1 12 Tf 72 770 Td (${text}) Tj ET`
  objects.push(
    `5 0 obj\n<< /Length ${stream.length} >>\nstream\n${stream}\nendstream\nendobj\n`
  )
  let body = "%PDF-1.4\n"
  const offsets: number[] = []
  for (const obj of objects) {
    offsets.push(body.length)
    body += obj
  }
  const xrefStart = body.length
  let xref = `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`
  for (const offset of offsets) {
    xref += `${String(offset).padStart(10, "0")} 00000 n \n`
  }
  const trailer = `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xrefStart}\n%%EOF\n`
  return Buffer.from(body + xref + trailer, "latin1")
}

test("pdf file upload ingests to processed", async ({ page }) => {
  await page.goto("/login")
  await page.getByLabel("E-Mail").fill(EMAIL)
  await page.getByLabel("Passwort").fill(PASSWORD)
  await page.getByRole("button", { name: "Anmelden" }).click()
  await expect(page).toHaveURL(/\/$/, { timeout: 20_000 })

  await page.goto("/intake")
  await page.getByLabel(/Antragstitel/).fill("E2E Upload Projekt")
  await page.getByRole("textbox", { name: /Projektidee/ }).fill("Eine Test-Projektidee für den PDF-Upload.")
  await page.getByText("Öffentlich", { exact: true }).click()
  await page.getByRole("button", { name: "Antrag anlegen" }).click()
  await expect(page).toHaveURL(/\/quellen/, { timeout: 20_000 })

  // Upload via the hidden file input of the source table.
  await page.locator('input[type="file"]').setInputFiles({
    name: "e2e-upload.pdf",
    mimeType: "application/pdf",
    buffer: minimalPdf("E2E upload smoke content for processing."),
  })
  await expect(page.getByRole("dialog", { name: "Datei hochladen" })).toBeVisible()
  await page.getByRole("button", { name: "Hochladen" }).click()

  // The source appears and becomes processed.
  await expect(page.getByText("e2e-upload.pdf")).toBeVisible({ timeout: 20_000 })
  await expect(page.getByText("Verarbeitet").first()).toBeVisible({
    timeout: 20_000,
  })

  // Refresh — the source persists.
  await page.reload()
  await expect(page.getByText("e2e-upload.pdf")).toBeVisible({ timeout: 20_000 })

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
  await page.getByRole("textbox", { name: /Projektidee/ }).fill("Projektidee mit Umlauten: äöüß.")
  await page.getByText("Öffentlich", { exact: true }).click()
  await page.getByRole("button", { name: "Antrag anlegen" }).click()
  await expect(page).toHaveURL(/\/quellen/, { timeout: 20_000 })

  await page.getByRole("button", { name: "Text einfügen" }).click()
  await page.getByLabel("Titel der Quelle").fill(UMLAUT_NAME)
  await page
    .getByLabel("Textinhalt")
    .fill("Müller & Söhne prüfen die Förderfähigkeit für größere Vorhaben. äöüÄÖÜß")
  await page.getByRole("button", { name: "Als Quelle hinzufügen" }).click()

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
