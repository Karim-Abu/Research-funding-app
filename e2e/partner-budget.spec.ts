import { test, expect } from "@playwright/test"

// Slice 1 end-to-end: Intake persists partners → Partner & Budget captures the
// structured budget → the deterministic budget rules evaluate with real inputs
// (no more automatic needs_input). Run + requirements read via the BFF API
// context (deterministic); intake + budget form are driven through the real UI.
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

  // 2. Intake with two named partners → project + persisted partners (B1).
  await page.goto("/intake")
  await page.getByText("Öffentlich", { exact: true }).click()
  await page.getByLabel(/Antragstitel/).fill("E2E Partner & Budget")
  await page.getByLabel(/Projektidee/).fill("Slice-1-Testprojekt mit Partnern und Budget.")
  await page.getByRole("button", { name: "Partner hinzufügen" }).click()
  await page.getByLabel("Partnername").fill("ETH Zürich")
  await page.getByRole("button", { name: "Partner hinzufügen" }).click()
  await page.getByLabel("Partnername").nth(1).fill("Empa")
  await page.getByRole("button", { name: "Antrag anlegen" }).click()
  await expect(page).toHaveURL(/\/quellen/, { timeout: 20_000 })

  // 3. Partner & Budget step lists the intake partners and takes the budget.
  await page.goto("/partner")
  await expect(page.getByText("ETH Zürich").first()).toBeVisible({ timeout: 20_000 })
  await expect(page.getByText("Empa").first()).toBeVisible()

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
