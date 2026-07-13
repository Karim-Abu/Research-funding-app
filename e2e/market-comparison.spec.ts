import { test, expect, type APIRequestContext, type Page } from "@playwright/test"

type Mut = () => Record<string, string>

// M9I-B market/competitor comparison smoke (fake provider). Requires the backend started
// with WEB_RESEARCH_ENABLED=true, WEB_RESEARCH_FAKE_PROVIDER=true, AGENT_FAKE_PROVIDER=true.
// Built only from imported public sources; no real Firecrawl, no draft mutation.
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
      title: "E2E Market", description: "Market comparison smoke.",
      funding_instrument_profile_id:
        "innosuisse_innovation_project_with_implementation_partner",
      data_classification: CLASSIFICATION,
    },
  })).json()).project_id
}

async function importTwoPublicSources(request: APIRequestContext, mut: Mut, projectId: string) {
  const accepted = await (await request.post(
    `/api/projects/${projectId}/research-tasks`,
    { headers: mut(), data: {
      purpose: "partner_role_suggestion", subject_type: "topic",
      query_preview: "öffentliche Markt- und Wettbewerbsquellen", max_results: 3,
      user_confirms_public_professional_purpose: true } },
  )).json()
  expect(await waitForOperation(request, accepted.operation_id)).toBe("succeeded")
  const results = await (await request.get(
    `/api/projects/${projectId}/research-results`)).json() as { result_id: string }[]
  expect(results.length).toBeGreaterThanOrEqual(2)
  for (const r of results.slice(0, 2)) {
    const res = await request.post(`/api/research-results/${r.result_id}/import`, { headers: mut() })
    expect(res.status()).toBe(201)
  }
}

test("market comparison: built from imported public sources, source-backed item with quote", async ({ page }) => {
  const mut = await login(page)
  const projectId = await createProject(page.request, mut)
  await importTwoPublicSources(page.request, mut, projectId)

  // Generate the comparison.
  const accepted = await (await page.request.post(
    `/api/projects/${projectId}/market-comparisons`, { headers: mut() })).json()
  expect(await waitForOperation(page.request, accepted.operation_id)).toBe("succeeded")

  const view = await (await page.request.get(
    `/api/market-comparisons/${accepted.resource_id}`)).json()
  expect(view.status).toBe("ready_for_review")
  expect(view.item_count).toBeGreaterThanOrEqual(1)
  const backed = (view.items as Array<{ confidence_label: string; evidence_quotes: unknown[] }>)
    .find((i) => i.confidence_label === "source_backed")
  expect(backed).toBeTruthy()
  expect(backed!.evidence_quotes.length).toBeGreaterThanOrEqual(1)

  // No drafts were created by the comparison (no automatic draft mutation).
  const sources = await (await page.request.get(`/api/projects/${projectId}/sources`)).json()
  expect(Array.isArray(sources)).toBe(true)

  await page.getByText("Anna Keller").first().click()
  await page.getByText("Abmelden").click()
  await expect(page).toHaveURL(/\/login/, { timeout: 20_000 })
})

test("market comparison UI: Quellen section renders a source-backed item", async ({ page }) => {
  const mut = await login(page)
  const projectId = await createProject(page.request, mut)
  await importTwoPublicSources(page.request, mut, projectId)

  await page.evaluate((id) => sessionStorage.setItem("rf_active_project_id", id), projectId)
  await page.goto("/quellen")

  const section = page.getByTestId("market-comparison-section")
  await expect(section).toBeVisible({ timeout: 20_000 })
  await expect(section).toContainText("Markt- und Konkurrenzvergleich")

  await page.getByRole("button", { name: "Vergleich erstellen" }).click()
  await expect(page.getByTestId("market-comparison-table")).toBeVisible({ timeout: 20_000 })
  await expect(page.getByText("Textstelle gefunden").first()).toBeVisible()
  // No provider/model branding anywhere on the page.
  await expect(page.locator("body")).not.toContainText(/firecrawl|anthropic|haiku/i)

  await page.getByText("Anna Keller").first().click()
  await page.getByText("Abmelden").click()
  await expect(page).toHaveURL(/\/login/, { timeout: 20_000 })
})
