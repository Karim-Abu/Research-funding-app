import { test, expect, type APIRequestContext, type Page } from "@playwright/test"

type Mut = () => Record<string, string>

// M9I-A public web research smoke (fake provider). Requires the backend started with
// WEB_RESEARCH_ENABLED=true, WEB_RESEARCH_FAKE_PROVIDER=true and AGENT_FAKE_PROVIDER=true
// (the A1 synthesis). No real Firecrawl is ever contacted.
const EMAIL = process.env.E2E_EMAIL ?? "anna.keller@example.test"
const PASSWORD = process.env.E2E_PASSWORD ?? "changeme-dev-lead"
const ORIGIN = "http://localhost:3000"
const CLASSIFICATION = {
  sensitivity: "public", origin: "synthetic", processing_mode: "cloud_assisted",
  web_research_mode: "validated_public", nda_applies: false,
}

function idem(): string {
  return Math.random().toString(36).slice(2) + Date.now().toString(36)
}

async function waitForOperation(request: APIRequestContext, opId: string): Promise<string> {
  let status = ""
  for (let i = 0; i < 60; i++) {
    status = (await (await request.get(`/api/operations/${opId}`)).json()).status
    if (["succeeded", "failed", "cancelled"].includes(status)) break
    await new Promise((r) => setTimeout(r, 500))
  }
  return status
}

async function login(page: Page): Promise<Mut> {
  await page.goto("/login")
  await page.getByLabel("E-Mail").fill(EMAIL)
  await page.getByLabel("Passwort").fill(PASSWORD)
  await page.getByRole("button", { name: "Anmelden" }).click()
  await expect(page).toHaveURL(/\/$/, { timeout: 20_000 })
  const csrf = (await (await page.request.get("/api/session")).json()).csrf_token as string
  return () => ({
    "X-CSRF-Token": csrf, Origin: ORIGIN, "Idempotency-Key": idem(),
    "Content-Type": "application/json",
  })
}

async function createProject(request: APIRequestContext, mut: Mut): Promise<string> {
  return (await (await request.post("/api/projects", {
    headers: mut(),
    data: {
      title: "E2E Web Research", description: "Public web research smoke.",
      funding_instrument_profile_id:
        "innosuisse_innovation_project_with_implementation_partner",
      data_classification: CLASSIFICATION,
    },
  })).json()).project_id
}

test("public research: search, import as source, deterministic analysis can use it", async ({ page }) => {
  const mut = await login(page)
  const projectId = await createProject(page.request, mut)

  // Start a research task and wait for candidates.
  const accepted = await (await page.request.post(
    `/api/projects/${projectId}/research-tasks`,
    { headers: mut(), data: {
      purpose: "partner_role_suggestion", subject_type: "topic",
      query_preview: "öffentliche Forschungskompetenz Photonik", max_results: 3,
      user_confirms_public_professional_purpose: true } },
  )).json()
  expect(await waitForOperation(page.request, accepted.operation_id)).toBe("succeeded")

  const results = await (await page.request.get(
    `/api/projects/${projectId}/research-results`)).json() as { result_id: string; status: string }[]
  expect(results.length).toBeGreaterThan(0)

  // Import the first candidate as a normal source.
  const imported = await page.request.post(
    `/api/research-results/${results[0].result_id}/import`, { headers: mut() })
  expect(imported.status()).toBe(201)
  const source = await imported.json()
  expect(source.type).toBe("url")
  expect(source.status).toBe("processed")
  const versionId = source.current_source_version_id as string
  expect(versionId).toBeTruthy()

  // The imported source appears in the project's source list.
  const sources = await (await page.request.get(
    `/api/projects/${projectId}/sources`)).json() as { source_id: string }[]
  expect(sources.some((s) => s.source_id === source.source_id)).toBe(true)

  // The deterministic evidence pipeline can use the imported source in an analysis run.
  const run = await (await page.request.post(`/api/projects/${projectId}/runs`, {
    headers: mut(), data: { settings: {
      processing_mode: "deterministic_only", max_cost_chf: 0, max_llm_calls: 0,
      max_web_calls: 0, source_version_ids: [versionId] } },
  })).json()
  expect(await waitForOperation(page.request, run.operation_id)).toBe("succeeded")

  await page.getByText("Anna Keller").first().click()
  await page.getByText("Abmelden").click()
  await expect(page).toHaveURL(/\/login/, { timeout: 20_000 })
})

test("public research panel: run + import from the Quellen UI, no provider branding", async ({ page }) => {
  const mut = await login(page)
  const projectId = await createProject(page.request, mut)

  await page.evaluate((id) => sessionStorage.setItem("rf_active_project_id", id), projectId)
  await page.goto("/quellen")

  const panel = page.getByTestId("public-research-panel")
  await expect(panel).toBeVisible({ timeout: 20_000 })
  await expect(panel).toContainText("Öffentliche Recherche")
  await expect(panel).toContainText("Keine vertraulichen oder personenbezogenen")

  await page.getByPlaceholder(/öffentliche Forschungskompetenz/i).fill("Photonik Kompetenz")
  await page.getByRole("button", { name: "Suchen" }).click()

  const importBtn = page.getByRole("button", { name: "Quelle importieren" }).first()
  await expect(importBtn).toBeVisible({ timeout: 20_000 })
  await importBtn.click()
  await expect(page.getByText("Als Quelle gespeichert").first()).toBeVisible({ timeout: 20_000 })

  // No provider/API terminology anywhere on the page.
  await expect(page.locator("body")).not.toContainText(/firecrawl/i)

  await page.getByText("Anna Keller").first().click()
  await page.getByText("Abmelden").click()
  await expect(page).toHaveURL(/\/login/, { timeout: 20_000 })
})
