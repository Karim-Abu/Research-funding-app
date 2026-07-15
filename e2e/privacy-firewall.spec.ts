import { test, expect, type APIRequestContext, type Page } from "@playwright/test"

// M9J Search Query Firewall (fake provider). Requires the backend started with
// WEB_RESEARCH_ENABLED=true, WEB_RESEARCH_FAKE_PROVIDER=true, AGENT_FAKE_PROVIDER=true.
// Seit dem Brief-Gate: Research-Tasks laufen NUR über brief-gebundene, menschlich
// freigegebene Queries. Flow A: D0 mit Brief-Query. Flow B: D2 — der Standalone-
// Firewall-Preview bereinigt (kein Roh-Leak), aber seine Freigabe genügt NICHT
// für einen Task (Brief-Provenienz Pflicht); brief-geplante Queries tragen nie
// Partner-/Budgetbezeichner. Flow C: D3/UNKNOWN blocked.
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


/** Brief anlegen + freigeben + Queries planen + freigeben (Provenienz-Pflicht). */
async function approvedBriefQuery(
  request: APIRequestContext, mut: Mut, projectId: string, modules: string[]
): Promise<string> {
  const brief = await (await request.put(`/api/projects/${projectId}/research-brief`, {
    headers: mut(),
    data: {
      application_domain: "Robotik-Messtechnik",
      technology_class: "Automatisierungssoftware",
      target_customer_segments: ["Industrieanwender"],
      region: "Schweiz",
      competence_needs: ["Robotik"],
      modules,
    },
  })).json()
  const briefId = brief.research_brief_id as string
  expect((await request.post(`/api/research-briefs/${briefId}/approve`, { headers: mut() })).ok()).toBeTruthy()
  const plan = await (await request.post(
    `/api/research-briefs/${briefId}/queries/plan`, { headers: mut() })).json()
  const first = (plan.queries as Array<{ approval_id: string; query_text: string }>)[0]
  expect(first).toBeTruthy()
  expect((await request.post(
    `/api/search-query-approvals/${first.approval_id}/approve`, { headers: mut() })).ok()).toBeTruthy()
  return first.approval_id
}

test("Flow A: D0 public web research works as before", async ({ page }) => {
  const mut = await login(page)
  const pid = await createProject(page.request, mut, dc("public", "synthetic"))
  const approvalId = await approvedBriefQuery(
    page.request, mut, pid, ["swiss_research_partners"]
  )
  const res = await page.request.post(`/api/projects/${pid}/research-tasks`, {
    headers: mut(), data: taskBody("öffentliche Wettbewerbsanalyse Robotik", approvalId),
  })
  expect(res.status()).toBe(202)
  expect(await waitForOperation(page.request, (await res.json()).operation_id)).toBe("succeeded")
})

test("Flow B (API): D2 — Preview bereinigt ohne Roh-Leak; Tasks verlangen Brief-Provenienz", async ({ page }) => {
  const mut = await login(page)
  const pid = await createProject(page.request, mut, dc("confidential", "real_project"), 500000)
  await addPartner(page.request, mut, pid)

  // Standalone-Firewall-Preview: bereinigt Partnername + Budget (kein Roh-Leak).
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

  // Diese Freigabe hat KEINE Brief-Provenienz — ein Research-Task damit wird
  // abgelehnt (kein Bypass des geprüften Briefs).
  const rejected = await page.request.post(`/api/projects/${pid}/research-tasks`, {
    headers: mut(), data: taskBody(D2_QUERY, preview.approval_id),
  })
  expect(rejected.status()).toBe(422)
  expect(await rejected.text()).toContain("research_brief_approval_required")

  // Der legitime Weg: brief-geplante Queries tragen nie Partner-/Budgetwerte.
  const approvalId = await approvedBriefQuery(
    page.request, mut, pid, ["swiss_research_partners"]
  )
  const created = await page.request.post(`/api/projects/${pid}/research-tasks`, {
    headers: mut(), data: taskBody(D2_QUERY, approvalId),
  })
  expect(created.status()).toBe(202)
  expect(await waitForOperation(page.request, (await created.json()).operation_id)).toBe("succeeded")

  const results = await page.request.get(`/api/projects/${pid}/research-results`)
  const text = await results.text()
  expect(text).not.toContain("Acme")
  expect(text).not.toContain("500'000")
  const rows = JSON.parse(text) as { result_id: string }[]
  expect(rows.length).toBeGreaterThanOrEqual(1)

  // Demo-Ergebnisse sind keine Webquellen — Import ehrlich verweigert.
  const imported = await page.request.post(
    `/api/research-results/${rows[0].result_id}/import`, { headers: mut() })
  expect(imported.status()).toBe(422)
  expect(await imported.text()).toContain("demo_result_not_importable")

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

test("Flow B (UI): vertrauliches Projekt — Queries entstehen nur aus dem Brief, ohne vertrauliche Bezeichner", async ({ page }) => {
  const mut = await login(page)
  const pid = await createProject(page.request, mut, dc("confidential", "real_project"), 500000)
  await addPartner(page.request, mut, pid)
  await approvedBriefQuery(page.request, mut, pid, ["market_growth"])

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
  // Public-safe Leitplanke: keine Rohidee/Partnernamen/Budgets in den Brief.
  await expect(panel).toContainText(
    "Keine Rohprojektidee, Partnernamen, Budgets oder Kontaktangaben"
  )
  await expect(panel.getByText("Brief v1 freigegeben")).toBeVisible()

  // Die geplante Query stammt aus dem Brief-Vokabular — vertrauliche
  // Bezeichner (Partnername, Budgetzahl) erscheinen nirgends.
  const rows = panel.getByTestId("query-approval-row")
  await expect(rows.first()).toBeVisible({ timeout: 20_000 })
  await expect(panel).not.toContainText("Acme")
  await expect(panel).not.toContainText("500")
  // No provider/model branding.
  await expect(page.locator("body")).not.toContainText(/firecrawl|anthropic|haiku/i)

  await page.getByText("Anna Keller").first().click()
  await page.getByText("Abmelden").click()
})
