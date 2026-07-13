import path from "node:path"
import { test, expect, type Page } from "@playwright/test"

// Innolink-Antragsimport über den vereinfachten Intake: PDF-only-Start →
// Projekt anlegen → Import-Review (adoptiert die hochgeladene Quelle) →
// Übernahme VOR jedem Analyse-Lauf → der spätere Lauf konsumiert den
// übernommenen Text als Entwurfsbasis → Fix Queue. Deterministisch
// (Fake-Provider, synthetisches Fixture «SmartGrid Optimizer»).
const EMAIL = process.env.E2E_EMAIL ?? "anna.keller@example.test"
const PASSWORD = process.env.E2E_PASSWORD ?? "changeme-dev-lead"
const ORIGIN = "http://localhost:3000"
const FIXTURE_PDF = path.join(
  __dirname, "..", "spike", "fixtures", "innolink_sample.pdf"
)

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

/** Öffentliche Demo-Daten: Stufe über den kompakten «Ändern»-Dialog wählen. */
async function choosePublic(page: Page) {
  await page.getByRole("button", { name: "Ändern" }).click()
  const dialog = page.getByRole("dialog")
  await dialog.getByText("Öffentlich", { exact: true }).click()
  await dialog.getByRole("button", { name: "Fertig" }).click()
  await expect(dialog).toBeHidden()
}

/** Deterministischen Analyse-Lauf via API starten und auf Abschluss warten. */
async function runAnalysis(page: Page, projectId: string): Promise<string> {
  const session = await page.request.get("/api/session")
  const csrf = (await session.json()).csrf_token as string
  const runRes = await page.request.post(`/api/projects/${projectId}/runs`, {
    headers: {
      "X-CSRF-Token": csrf,
      Origin: ORIGIN,
      "Idempotency-Key": idem(),
      "Content-Type": "application/json",
    },
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
  for (let i = 0; i < 40; i++) {
    const op = await page.request.get(`/api/operations/${accepted.operation_id}`)
    opStatus = (await op.json()).status
    if (["succeeded", "failed", "cancelled"].includes(opStatus)) break
    await page.waitForTimeout(300)
  }
  expect(opStatus).toBe("succeeded")
  return accepted.resource_id as string
}

test("Import-Flow: PDF-only-Start → Übernahme VOR dem Run → Baseline → Fix Queue", async ({ page }) => {
  await login(page)

  // --- Intake: nur das PDF — kein Pfadzwang, Titel aus dem Dateinamen -------
  await page.goto("/intake")
  await page.getByTestId("intake-file-input").setInputFiles(FIXTURE_PDF)
  await expect(page.getByLabel(/Projekttitel/)).toHaveValue("innolink_sample")
  await choosePublic(page)
  await page.getByRole("button", { name: "Projekt erstellen und weiter" }).click()

  // Das Intake lädt hoch und übergibt die Quelle an den Import-Review.
  await expect(page).toHaveURL(/\/import\?source=/, { timeout: 20_000 })

  // --- Review-Tabelle: 8 Kandidaten, Unsicher markiert, nichts vorentschieden
  await expect(page.getByTestId("import-review")).toBeVisible({ timeout: 60_000 })
  await expect(page.getByTestId("import-candidate")).toHaveCount(8)
  await expect(page.getByText("Unsicher — Prüfung nötig").first()).toBeVisible()
  await expect(page.getByText("Übernommen", { exact: true })).toHaveCount(0)

  // --- Fachliche Korrektur: KEIN «Analyse starten»-Gate mehr -----------------
  await expect(page.getByTestId("import-start-run")).toHaveCount(0)
  await expect(
    page.getByText(/fliessen beim nächsten Analyse-Lauf als/)
  ).toBeVisible()

  // --- Übernahme des Abstracts VOR jedem Run ---------------------------------
  const abstractRow = page
    .getByTestId("import-candidate")
    .filter({ hasText: "Abstract" })
    .first()
  await abstractRow.getByRole("button", { name: "Übernehmen", exact: true }).click()
  await expect(abstractRow.getByText("Übernommen", { exact: true })).toBeVisible({
    timeout: 20_000,
  })

  // --- Der spätere Lauf konsumiert die Übernahme als Entwurfsbasis -----------
  const projectId = await page.evaluate(() =>
    window.sessionStorage.getItem("rf_active_project_id")
  )
  expect(projectId).toBeTruthy()
  const runId = await runAnalysis(page, projectId as string)
  const draft = await (
    await page.request.get(`/api/runs/${runId}/fields/INTRO.APP.ABSTRACT`)
  ).json()
  expect(draft.current_version.created_by).toBe("import")
  expect(draft.current_version.text).toContain("Das Projekt entwickelt")
  expect(draft.status).toBe("needs_review")

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

test("Intake kombiniert Idee + PDF: description ist die getippte Idee", async ({ page }) => {
  await login(page)

  await page.goto("/intake")
  await page.getByLabel(/Projekttitel/).fill("Kombi-Start E2E")
  await page
    .getByRole("textbox", { name: /Projektidee/ })
    .fill("Eine kombinierte Projektidee für den E2E-Test.")
  await page.getByTestId("intake-file-input").setInputFiles(FIXTURE_PDF)
  // Der eingegebene Titel bleibt erhalten (kein Prefill-Überschreiben).
  await expect(page.getByLabel(/Projekttitel/)).toHaveValue("Kombi-Start E2E")
  await choosePublic(page)
  await page.getByRole("button", { name: "Projekt erstellen und weiter" }).click()
  await expect(page).toHaveURL(/\/import\?source=/, { timeout: 20_000 })

  const projectId = await page.evaluate(() =>
    window.sessionStorage.getItem("rf_active_project_id")
  )
  expect(projectId).toBeTruthy()
  const project = await (
    await page.request.get(`/api/projects/${projectId}`)
  ).json()
  expect(project.title).toBe("Kombi-Start E2E")
  expect(project.description).toBe(
    "Eine kombinierte Projektidee für den E2E-Test."
  )
})

async function createIdeaProject(page: Page, title: string) {
  await page.goto("/intake")
  await page.getByLabel(/Projekttitel/).fill(title)
  await page
    .getByRole("textbox", { name: /Projektidee/ })
    .fill("Projektidee für den Upload-Phasen-Test.")
  await choosePublic(page)
  await page.getByRole("button", { name: "Projekt erstellen und weiter" }).click()
  await expect(page).toHaveURL(/\/quellen/, { timeout: 20_000 })
}

/** Nach einem harten Seitenload erst hochladen, wenn die Session-Bootstrap
 *  fertig ist (User-Chip sichtbar) — der CSRF-Token liegt nur im Speicher. */
async function waitForImportUploadReady(page: Page) {
  await expect(page.getByText("Anna Keller").first()).toBeVisible({
    timeout: 20_000,
  })
  await expect(page.getByText("Datei auswählen")).toBeVisible({
    timeout: 20_000,
  })
}

test("Import-Upload zeigt nachvollziehbare Phasen bis zum Review", async ({ page }) => {
  await login(page)
  await createIdeaProject(page, "E2E Import-Phasen")

  await page.goto("/import")
  await waitForImportUploadReady(page)
  await page.getByTestId("import-file-input").setInputFiles(FIXTURE_PDF)

  // Phasenanzeige: Parsing ist phasenbasiert sichtbar (kein Fake-Prozent).
  await expect(page.getByTestId("import-progress")).toBeVisible({
    timeout: 20_000,
  })
  await expect(page.getByText("Text wird extrahiert")).toBeVisible()

  await expect(page.getByTestId("import-review")).toBeVisible({ timeout: 60_000 })
  await expect(page.getByTestId("import-candidate")).toHaveCount(8)
})

test("Import-Upload-Fehler: Ursache, Erneut versuchen und Technische Details", async ({ page }) => {
  await login(page)
  await createIdeaProject(page, "E2E Import-Fehler")

  await page.goto("/import")
  await waitForImportUploadReady(page)
  await page.getByTestId("import-file-input").setInputFiles({
    name: "kaputt.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from("definitiv kein pdf inhalt"),
  })

  // Ursachen-spezifische Meldung (Signatur passt nicht zur Endung) statt
  // einer generischen Sammel-Fehlermeldung.
  await expect(
    page.getByText(/wird nicht unterstützt oder der Inhalt passt nicht zur Dateiendung/)
  ).toBeVisible({ timeout: 20_000 })
  await expect(
    page.getByRole("button", { name: "Erneut versuchen" })
  ).toBeVisible()

  // Correlation-ID/Fehlercode nur eingeklappt unter «Technische Details».
  await page.getByRole("button", { name: "Technische Details" }).click()
  await expect(page.getByText("unsupported_media_type")).toBeVisible()

  // Retry mit derselben Datei führt ehrlich erneut zum selben Fehler.
  await page.getByRole("button", { name: "Erneut versuchen" }).click()
  await expect(
    page.getByText(/wird nicht unterstützt oder der Inhalt passt nicht zur Dateiendung/)
  ).toBeVisible({ timeout: 20_000 })
})
