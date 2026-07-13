import { test, expect } from "@playwright/test"

// Slice 1 end-to-end: Partner & Budget ist der EINZIGE Erfassungsort für
// Partner (keine Doppelerfassung im Intake mehr) → the deterministic budget
// rules evaluate with real inputs (no more automatic needs_input). Run +
// requirements read via the BFF API context (deterministic); intake, partner
// and budget form are driven through the real UI.
// Local run: pnpm exec playwright test e2e/partner-budget.spec.ts
// (requires uvicorn :8000 + APP_BACKEND_MODE=live pnpm dev :3000).
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

function idem(): string {
  return Math.random().toString(36).slice(2) + Date.now().toString(36)
}

test("intake partners + budget feed the requirements precheck", async ({ page }) => {
  // 1. Login
  await page.goto("/login")
  await page.getByLabel("E-Mail").fill(EMAIL)
  await page.getByLabel("Passwort").fill(PASSWORD)
  await page.getByRole("button", { name: "Anmelden" }).click()
  await expect(page).toHaveURL(/\/$/, { timeout: 20_000 })

  // 2. Vereinfachter Intake: keine Partner-Eingaben mehr erreichbar.
  await page.goto("/intake")
  await page.getByLabel(/Projekttitel/).fill("E2E Partner & Budget")
  await page.getByRole("textbox", { name: /Projektidee/ }).fill("Slice-1-Testprojekt mit Partnern und Budget.")
  await expect(
    page.getByRole("button", { name: "Partner hinzufügen" })
  ).toHaveCount(0)
  await expect(
    page.getByText("Partner und Budget ergänzen Sie im nächsten Schritt.")
  ).toBeVisible()
  // Öffentliche Demo-Daten über den kompakten «Ändern»-Dialog.
  await page.getByRole("button", { name: "Ändern" }).click()
  const dialog = page.getByRole("dialog")
  await dialog.getByText("Öffentlich", { exact: true }).click()
  await dialog.getByRole("button", { name: "Fertig" }).click()
  await expect(dialog).toBeHidden()
  await page.getByRole("button", { name: "Projekt erstellen und weiter" }).click()
  await expect(page).toHaveURL(/\/quellen/, { timeout: 20_000 })

  // 3. Partner & Budget ist der Erfassungsort: Partner anlegen + Budget.
  await page.goto("/partner")
  const addPartner = page.getByRole("button", { name: "Partner hinzufügen" })

  // MVP-Pflichtfelder: der Submit erklärt, was noch fehlt.
  await expect(addPartner).toBeDisabled()
  await expect(page.getByText(/Noch offen:/)).toBeVisible()

  async function fillPartner(name: string, role: string) {
    await page.getByLabel("Name").fill(name)
    await page.getByLabel("Land").fill("CH")
    await page.getByLabel("Rolle im Projekt").fill(role)
    await page.getByLabel("Kompetenz & Beitrag (kurz)").fill(
      "Einschlägige Kompetenz für den Demo-Workflow."
    )
  }

  await fillPartner("ETH Zürich", "Grundlagenforschung")
  await addPartner.click()
  await expect(page.getByText("ETH Zürich").first()).toBeVisible({ timeout: 20_000 })
  await fillPartner("Empa", "Materialtests")
  await addPartner.click()
  await expect(page.getByText("Empa").first()).toBeVisible({ timeout: 20_000 })

  // Partner BEARBEITEN: Rolle ändern, Änderung sichtbar.
  await page.getByRole("button", { name: "Partner Empa bearbeiten" }).click()
  await page.getByLabel("Rolle im Projekt").fill("Materialtests und Validierung")
  await page.getByRole("button", { name: "Änderungen speichern" }).click()
  await expect(
    page.getByText("Materialtests und Validierung").first()
  ).toBeVisible({ timeout: 20_000 })

  // «Angabe nötig» erzwingt einen Kommentar (kein erfundenes Urteil) und
  // markiert den Partner mit «Menschliche Prüfung erforderlich».
  await fillPartner("Startup GmbH", "Pilotierung")
  await page
    .getByRole("button", { name: "Unabhängigkeit (Detailangaben)" })
    .click()
  await page
    .getByLabel("Personelle Unabhängigkeit")
    .selectOption("needs_input")
  await expect(addPartner).toBeDisabled()
  await expect(
    page.getByText("Noch offen: Kommentar zur Einstufung.")
  ).toBeVisible()
  await page
    .getByLabel("Kommentar zur Einstufung")
    .fill("Beteiligungsverhältnisse werden noch geklärt.")
  await addPartner.click()
  await expect(
    page.getByText("Menschliche Prüfung erforderlich").first()
  ).toBeVisible({ timeout: 20_000 })

  await page
    .getByLabel("Direkte Projektkosten (ohne Overhead)")
    .fill("100000")
  await page.getByLabel("Eigenleistung Umsetzungspartner").fill("45000")
  await page.getByLabel("Barbeitrag (Cash)").fill("5000")
  await page.getByLabel("Projektdauer (Monate)").fill("24")
  await page.getByRole("button", { name: "Budget speichern" }).click()
  await expect(page.getByText("Budgetangaben gespeichert.")).toBeVisible({
    timeout: 20_000,
  })

  // 3b. Formale Vorprüfung erscheint SOFORT (ohne Analyse-Lauf), gerechnet
  // vom Backend-Rule-Kern: 50 % Umsetzungsanteil + 5 % Barbeitrag → Erfüllt.
  const precheck = page.getByTestId("budget-precheck")
  await expect(precheck.getByText("Erfüllt", { exact: true })).toHaveCount(2, {
    timeout: 20_000,
  })
  await expect(precheck.getByTestId("precheck-contribution")).toContainText("50")
  await expect(precheck.getByTestId("precheck-cash")).toContainText("5 %")

  // 4. Source + run via the API context (deterministic).
  const session = await page.request.get("/api/session")
  const csrf = (await session.json()).csrf_token as string
  const mut = () => ({
    "X-CSRF-Token": csrf,
    Origin: ORIGIN,
    "Idempotency-Key": idem(),
    "Content-Type": "application/json",
  })
  const projectId = await page.evaluate(() =>
    window.sessionStorage.getItem("rf_active_project_id")
  )
  expect(projectId).toBeTruthy()

  const src = await page.request.post(`/api/projects/${projectId}/sources/text`, {
    headers: mut(),
    data: {
      name: "Notiz",
      text: "Source content for the run.",
      data_classification: CLASSIFICATION,
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
  for (let i = 0; i < 40; i++) {
    const op = await page.request.get(`/api/operations/${accepted.operation_id}`)
    opStatus = (await op.json()).status
    if (["succeeded", "failed", "cancelled"].includes(opStatus)) break
    await page.waitForTimeout(300)
  }
  expect(opStatus).toBe("succeeded")

  // 5. Budget rules now evaluate from real inputs: 50% share (45k+5k of 100k)
  // and 5% cash are no longer needs_input (human review keeps them partial).
  const reqRes = await page.request.get(
    `/api/runs/${accepted.resource_id}/requirements`
  )
  expect(reqRes.status()).toBe(200)
  const byId = Object.fromEntries(
    ((await reqRes.json()) as Array<{ requirement_id: string; status: string }>).map(
      (a) => [a.requirement_id, a.status]
    )
  )
  expect(["fulfilled", "partial"]).toContain(
    byId["REQ.INNO.BUDGET.IMPLEMENTATION_SHARE_40_60"]
  )
  expect(["fulfilled", "partial"]).toContain(byId["REQ.INNO.BUDGET.CASH_MIN5"])

  // 6. UI smoke: the requirements workspace renders for this run.
  await page.goto("/anforderungen")
  await expect(page.getByText("Fördervoraussetzungen").first()).toBeVisible({
    timeout: 20_000,
  })

  await page.getByText("Anna Keller").first().click()
  await page.getByText("Abmelden").click()
  await expect(page).toHaveURL(/\/login/, { timeout: 20_000 })
})
