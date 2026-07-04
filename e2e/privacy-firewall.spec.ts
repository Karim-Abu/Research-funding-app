import { test, expect, type APIRequestContext, type Page } from "@playwright/test"

// M9J Search Query Firewall (fake provider). Requires the backend started with
// WEB_RESEARCH_ENABLED=true, WEB_RESEARCH_FAKE_PROVIDER=true, AGENT_FAKE_PROVIDER=true.
// Flow A: D0 public query works. Flow B: D2 query with partner+budget → sanitize →
// approve → search with sanitized query → import. Flow C: D3/UNKNOWN blocked.
type Mut = () => Record<string, string>

const EMAIL = process.env.E2E_EMAIL ?? "anna.keller@example.test"
const PASSWORD = process.env.E2E_PASSWORD ?? "changeme-dev-lead"
const ORIGIN = "http://localhost:3000"
const PROFILE = "innosuisse_innovation_project_with_implementation_partner"
const PARTNER = "Acme Robotics AG"
const D2_QUERY = "Wettbewerber für Acme Robotics AG mit Budget CHF 500'000"

function dc(sensitivity: string, origin: string, nda = false) {
  return {
    sensitivity, origin, processing_mode: "cloud_assisted",
    web_research_mode: "validated_public", nda_applies: nda,
  }
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

async function createProject(
  request: APIRequestContext, mut: Mut, classification: object, budget?: number
): Promise<string> {
  const data: Record<string, unknown> = {
    title: "E2E Firewall", description: "Firewall smoke.",
    funding_instrument_profile_id: PROFILE, data_classification: classification,
  }
  if (budget !== undefined) data.budget_framework_chf = budget
  return (await (await request.post("/api/projects", { headers: mut(), data })).json()).project_id
}

async function addPartner(request: APIRequestContext, mut: Mut, projectId: string) {
  const res = await request.post(`/api/projects/${projectId}/partners`, {
    headers: mut(), data: { name: PARTNER, partner_type: "implementation_partner" },
  })
  expect(res.status()).toBe(201)
}

function taskBody(query: string, approvalId?: string) {
  const body: Record<string, unknown> = {
    purpose: "partner_role_suggestion", subject_type: "topic",
    query_preview: query, max_results: 3, user_confirms_public_professional_purpose: true,
  }
  if (approvalId) body.approval_id = approvalId
  return body
}

test("Flow A: D0 public web research works as before", async ({ page }) => {
  const mut = await login(page)
  const pid = await createProject(page.request, mut, dc("public", "synthetic"))
  const res = await page.request.post(`/api/projects/${pid}/research-tasks`, {
    headers: mut(), data: taskBody("öffentliche Wettbewerbsanalyse Robotik"),
  })
  expect(res.status()).toBe(202)
  expect(await waitForOperation(page.request, (await res.json()).operation_id)).toBe("succeeded")
})

test("Flow B (API): D2 query sanitized, approved, searched, imported — no raw leak", async ({ page }) => {
  const mut = await login(page)
  const pid = await createProject(page.request, mut, dc("confidential", "real_project"), 500000)
  await addPartner(page.request, mut, pid)

  const preview = await (await page.request.post(
    `/api/projects/${pid}/search-query-firewall/preview`,
    { headers: mut(), data: { raw_query: D2_QUERY } })).json()
  expect(preview.decision).toBe("require_human_approval")
  expect(preview.approval_id).toBeTruthy()
  expect(preview.sanitized_query).not.toContain("Acme")
  expect(preview.sanitized_query).not.toContain("500")

  const approved = await page.request.post(
    `/api/search-query-approvals/${preview.approval_id}/approve`, { headers: mut() })
  expect(approved.status()).toBe(200)

  const created = await page.request.post(`/api/projects/${pid}/research-tasks`, {
    headers: mut(), data: taskBody(D2_QUERY, preview.approval_id),
  })
  expect(created.status()).toBe(202)
  expect(await waitForOperation(page.request, (await created.json()).operation_id)).toBe("succeeded")

  const results = await page.request.get(`/api/projects/${pid}/research-results`)
  const text = await results.text()
  expect(text).not.toContain("Acme")
  expect(text).not.toContain("500'000")
  const rows = JSON.parse(text) as { result_id: string }[]
  expect(rows.length).toBeGreaterThanOrEqual(1)

  const imported = await page.request.post(
    `/api/research-results/${rows[0].result_id}/import`, { headers: mut() })
  expect(imported.status()).toBe(201)
  expect((await imported.json()).data_classification.origin).toBe("public_source")

  await page.getByText("Anna Keller").first().click()
  await page.getByText("Abmelden").click()
})

test("Flow C: D3 (NDA) and UNKNOWN web research are blocked", async ({ page }) => {
  const mut = await login(page)
  const d3 = await createProject(page.request, mut, dc("confidential", "real_project", true))
  const r1 = await page.request.post(`/api/projects/${d3}/research-tasks`, {
    headers: mut(), data: taskBody("irgendeine Anfrage"),
  })
  expect(r1.status()).toBe(403)

  // public sensitivity + real_project origin → UNKNOWN (deny-by-default).
  const unknown = await createProject(page.request, mut, dc("public", "real_project"))
  const r2 = await page.request.post(`/api/projects/${unknown}/research-tasks`, {
    headers: mut(), data: taskBody("irgendeine Anfrage"),
  })
  expect(r2.status()).toBe(403)
})

test("Flow B (UI): confidential panel previews, approves and searches the sanitized query", async ({ page }) => {
  const mut = await login(page)
  const pid = await createProject(page.request, mut, dc("confidential", "real_project"), 500000)
  await addPartner(page.request, mut, pid)

  await page.evaluate(
    ({ id }) => {
      sessionStorage.setItem("rf_active_project_id", id)
      sessionStorage.setItem("rf_current_intake", JSON.stringify({ vertraulichkeit: "confidential" }))
    },
    { id: pid }
  )
  await page.goto("/quellen")

  const panel = page.getByTestId("public-research-panel")
  await expect(panel).toBeVisible({ timeout: 20_000 })
  await expect(panel).toContainText("möglicherweise vertrauliche Angaben")

  await page.getByLabel("Öffentlicher Suchbegriff").fill(D2_QUERY)
  await page.getByRole("button", { name: "Vor Webrecherche prüfen" }).click()

  const preview = page.getByTestId("firewall-preview")
  await expect(preview).toBeVisible({ timeout: 20_000 })
  await expect(page.getByTestId("sanitized-query")).not.toContainText("Acme")
  await expect(preview).not.toContainText("500")
  // No provider/model branding.
  await expect(page.locator("body")).not.toContainText(/firecrawl|anthropic|haiku/i)

  await page.getByRole("button", { name: "Bereinigte Anfrage freigeben und suchen" }).click()
  await expect(page.getByTestId("research-results")).toBeVisible({ timeout: 20_000 })

  await page.getByText("Anna Keller").first().click()
  await page.getByText("Abmelden").click()
})
