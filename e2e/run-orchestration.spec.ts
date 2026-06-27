import { test, expect } from "@playwright/test"

// Technical run-orchestration smoke. The user-facing "Analyse starten" action is
// capability-disabled (features.runs=false) until M4, so the run is exercised
// through the BFF/API request context (not a misleading UI flow).
const EMAIL = process.env.E2E_EMAIL ?? "anna.keller@example.test"
const PASSWORD = process.env.E2E_PASSWORD ?? "changeme-dev-lead"
const ORIGIN = "http://localhost:3000"
const CLASSIFICATION = {
  sensitivity: "public",
  origin: "synthetic",
  processing_mode: "cloud_assisted",
  web_research_mode: "off",
  nda_applies: false,
}

function idem(): string {
  return Math.random().toString(36).slice(2) + Date.now().toString(36)
}

test("run orchestration technical smoke (API context)", async ({ page }) => {
  // 1. UI login establishes the session cookie in the browser context.
  await page.goto("/login")
  await page.getByLabel("E-Mail").fill(EMAIL)
  await page.getByLabel("Passwort").fill(PASSWORD)
  await page.getByRole("button", { name: "Anmelden" }).click()
  await expect(page).toHaveURL(/\/$/, { timeout: 20_000 })

  // 2. CSRF token from the session (page.request shares the cookie).
  const session = await page.request.get("/api/session")
  expect(session.ok()).toBeTruthy()
  const csrf = (await session.json()).csrf_token as string
  const mut = () => ({
    "X-CSRF-Token": csrf,
    Origin: ORIGIN,
    "Idempotency-Key": idem(),
    "Content-Type": "application/json",
  })

  // 3. Create a project + a processed text source.
  const projectRes = await page.request.post("/api/projects", {
    headers: mut(),
    data: {
      title: "E2E Run Project",
      description: "Technical orchestration smoke.",
      funding_instrument_profile_id:
        "innosuisse_innovation_project_with_implementation_partner",
      data_classification: CLASSIFICATION,
    },
  })
  expect(projectRes.status()).toBe(201)
  const projectId = (await projectRes.json()).project_id

  const sourceRes = await page.request.post(
    `/api/projects/${projectId}/sources/text`,
    {
      headers: mut(),
      data: {
        name: "Notiz",
        text: "E2E run source content for the technical workflow.",
        data_classification: CLASSIFICATION,
      },
    }
  )
  expect(sourceRes.status()).toBe(201)
  expect((await sourceRes.json()).status).toBe("processed")

  // 4. createRun → 202 AsyncAccepted.
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
  expect(accepted.resource_type).toBe("run")
  expect(["queued", "running"]).toContain(accepted.status)

  // 5. Poll the operation to a terminal technical state.
  let opStatus = ""
  for (let i = 0; i < 40; i++) {
    const op = await page.request.get(`/api/operations/${accepted.operation_id}`)
    opStatus = (await op.json()).status
    if (["succeeded", "failed", "cancelled"].includes(opStatus)) break
    await page.waitForTimeout(500)
  }
  expect(opStatus).toBe("succeeded")

  // 6. Run reached a terminal technical state.
  const run = await page.request.get(`/api/runs/${accepted.resource_id}`)
  expect((await run.json()).status).toBe("completed")

  // 7. Logout.
  await page.getByText("Anna Keller").first().click()
  await page.getByText("Abmelden").click()
  await expect(page).toHaveURL(/\/login/, { timeout: 20_000 })
})
