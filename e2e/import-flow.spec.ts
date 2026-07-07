import path from "node:path"
import { test, expect } from "@playwright/test"

// R3.3 — Innolink-Antragsimport: Upload → Review-Tabelle → Übernahme →
// Fix Queue. Deterministisch (Fake-Provider, synthetisches Fixture aus dem
// Gate-Spike — fiktives Projekt «SmartGrid Optimizer», Testdaten-Policy).
const EMAIL = process.env.E2E_EMAIL ?? "anna.keller@example.test"
const PASSWORD = process.env.E2E_PASSWORD ?? "changeme-dev-lead"
const ORIGIN = "http://localhost:3000"
const CLASSIFICATION = {
  sensitivity: "public",
  origin: "synthetic",
  processing_mode: "deterministic_only",
  web_research_mode: "off",
  nda_applies: false,
}
const FIXTURE_PDF = path.join(
  __dirname, "..", "spike", "fixtures", "innolink_sample.pdf"
)

function idem(): string {
  return Math.random().toString(36).slice(2) + Date.now().toString(36)
}

test("Import-Flow: Upload → Review → Übernahme → Fix Queue", async ({ page }) => {
  await page.goto("/login")
  await page.getByLabel("E-Mail").fill(EMAIL)
  await page.getByLabel("Passwort").fill(PASSWORD)
  await page.getByRole("button", { name: "Anmelden" }).click()
  await expect(page).toHaveURL(/\/$/, { timeout: 20_000 })

  // Intake zeigt die drei Startoptionen (R3.3).
  await page.goto("/intake")
  await expect(
    page.getByText("Bestehenden Innolink-Antrag hochladen")
  ).toBeVisible({ timeout: 20_000 })
  await expect(page.getByText("Mit Projektidee starten")).toBeVisible()
  await expect(page.getByText("Aus Notizen & Quellen starten")).toBeVisible()

  // Projekt per API anlegen (schneller/stabiler als das volle Intake).
  const api = page.request
  const csrf = (await (await api.get("/api/session")).json()).csrf_token as string
  const projectId = (await (await api.post("/api/projects", {
    headers: {
      "X-CSRF-Token": csrf,
      Origin: ORIGIN,
      "Idempotency-Key": idem(),
      "Content-Type": "application/json",
    },
    data: {
      title: "Import-Flow E2E",
      description: "R3.3 Import-E2E.",
      funding_instrument_profile_id:
        "innosuisse_innovation_project_with_implementation_partner",
      data_classification: CLASSIFICATION,
    },
  })).json()).project_id as string
  await page.evaluate(
    (pid) => sessionStorage.setItem("rf_active_project_id", pid),
    projectId
  )

  // --- Upload ---------------------------------------------------------------
  await page.goto("/import")
  await page.getByTestId("import-file-input").setInputFiles(FIXTURE_PDF)

  // --- Review-Tabelle: 8 Kandidaten, Unsicher markiert, nichts vorentschieden
  await expect(page.getByTestId("import-review")).toBeVisible({ timeout: 60_000 })
  await expect(page.getByTestId("import-candidate")).toHaveCount(8)
  await expect(page.getByText("Unsicher — Prüfung nötig").first()).toBeVisible()
  await expect(page.getByText("Übernommen", { exact: true })).toHaveCount(0)

  // --- Analyse starten (Entwürfe sind run-gebunden) --------------------------
  await page.getByTestId("import-start-run").click()
  await expect(page.getByTestId("import-start-run")).toHaveCount(0, {
    timeout: 60_000,
  })

  // --- Übernahme des Abstracts ------------------------------------------------
  const abstractRow = page
    .getByTestId("import-candidate")
    .filter({ hasText: "Abstract" })
    .first()
  await abstractRow.getByRole("button", { name: "Übernehmen" }).click()
  await expect(abstractRow.getByText("Übernommen", { exact: true })).toBeVisible({
    timeout: 20_000,
  })

  // --- Weiter zur Fix Queue («Nächste Aufgaben») ------------------------------
  await page.getByTestId("import-to-fix-queue").click()
  await expect(page).toHaveURL(/\/review/, { timeout: 20_000 })
  await expect(
    page.getByRole("heading", { name: "Qualitätsprüfung", exact: true })
  ).toBeVisible({ timeout: 20_000 })
  const guidance = page
    .getByTestId("fix-queue-next")
    .or(page.getByTestId("next-steps"))
    .first()
  await expect(guidance).toBeVisible({ timeout: 20_000 })
})
