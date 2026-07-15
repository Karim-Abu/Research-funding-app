import { test, expect, type APIRequestContext, type Page } from "@playwright/test"

type Mut = () => Record<string, string>

// M9I-A public web research smoke (fake provider). Requires the backend started with
// WEB_RESEARCH_ENABLED=true, WEB_RESEARCH_FAKE_PROVIDER=true and AGENT_FAKE_PROVIDER=true.
// EHRLICHER Fake-Modus (a2c9b1c): Queries entstehen NUR aus dem menschlich
// freigegebenen public-safe Recherchebrief; Demo-Ergebnisse sind klar markiert
// und werden NIE als Quelle importiert (API 422 «demo_result_not_importable»).
// No real Firecrawl is ever contacted.
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

/** Brief anlegen + freigeben + Queries planen; liefert die approval_ids. */
async function approvedQueryIds(
  request: APIRequestContext,
  mut: Mut,
  projectId: string,
  modules: string[]
): Promise<{ briefId: string; approvalIds: string[] }> {
  const brief = await (
    await request.put(`/api/projects/${projectId}/research-brief`, {
      headers: mut(),
      data: {
        application_domain: "Photonik-Messtechnik",
        technology_class: "Optische Sensorik",
        target_customer_segments: ["Industrieanwender"],
        region: "Schweiz",
        competence_needs: ["Photonik"],
        modules,
      },
    })
  ).json()
  const briefId = brief.research_brief_id as string
  expect(
    (await request.post(`/api/research-briefs/${briefId}/approve`, { headers: mut() })).ok()
  ).toBeTruthy()
  const plan = await (
    await request.post(`/api/research-briefs/${briefId}/queries/plan`, { headers: mut() })
  ).json()
  const approvalIds: string[] = []
  for (const query of plan.queries as Array<{ approval_id: string }>) {
    expect(
      (
        await request.post(
          `/api/search-query-approvals/${query.approval_id}/approve`,
          { headers: mut() }
        )
      ).ok()
    ).toBeTruthy()
    approvalIds.push(query.approval_id)
  }
  expect(approvalIds.length).toBeGreaterThan(0)
  return { briefId, approvalIds }
}

test("public research: brief-gebundene Suche liefert Demo-Kandidaten, Import wird ehrlich verweigert", async ({ page }) => {
  const mut = await login(page)
  const projectId = await createProject(page.request, mut)
  const { approvalIds } = await approvedQueryIds(
    page.request, mut, projectId, ["swiss_research_partners"]
  )

  // Research-Task nur mit freigegebener Brief-Query (approval_id).
  const accepted = await (await page.request.post(
    `/api/projects/${projectId}/research-tasks`,
    { headers: mut(), data: {
      purpose: "partner_role_suggestion", subject_type: "topic",
      query_preview: "öffentliche Forschungskompetenz Photonik", max_results: 3,
      user_confirms_public_professional_purpose: true,
      approval_id: approvalIds[0] } },
  )).json()
  expect(await waitForOperation(page.request, accepted.operation_id)).toBe("succeeded")

  const results = await (await page.request.get(
    `/api/projects/${projectId}/research-results`)).json() as { result_id: string; status: string }[]
  expect(results.length).toBeGreaterThan(0)
  expect(results.every((r) => r.status === "candidate")).toBe(true)

  // Demo-Ergebnisse sind KEINE Webquellen: Import wird auf API-Ebene verweigert.
  const imported = await page.request.post(
    `/api/research-results/${results[0].result_id}/import`, { headers: mut() })
  expect(imported.status()).toBe(422)
  expect(JSON.stringify(await imported.json())).toContain("demo_result_not_importable")

  // Es entsteht keine URL-Quelle; die deterministische Analyse läuft unabhängig.
  const sources = await (await page.request.get(
    `/api/projects/${projectId}/sources`)).json() as { type: string }[]
  expect(sources.some((s) => s.type === "url")).toBe(false)
  const run = await (await page.request.post(`/api/projects/${projectId}/runs`, {
    headers: mut(), data: { settings: {
      processing_mode: "deterministic_only", max_cost_chf: 0, max_llm_calls: 0,
      max_web_calls: 0 } },
  })).json()
  expect(await waitForOperation(page.request, run.operation_id)).toBe("succeeded")

  await page.getByText("Anna Keller").first().click()
  await page.getByText("Abmelden").click()
  await expect(page).toHaveURL(/\/login/, { timeout: 20_000 })
})

test("public research panel: Brief → Queries → Demo-Ergebnisse ohne Übernahme, kein Provider-Branding", async ({ page }) => {
  const mut = await login(page)
  const projectId = await createProject(page.request, mut)
  await approvedQueryIds(page.request, mut, projectId, ["market_growth"])

  await page.evaluate((id) => sessionStorage.setItem("rf_active_project_id", id), projectId)
  await page.goto("/quellen")

  const panel = page.getByTestId("public-research-panel")
  await expect(panel).toBeVisible({ timeout: 20_000 })
  await expect(panel).toContainText("Öffentliche Recherche")
  // Public-safe Leitplanke des Brief-Workflows.
  await expect(panel).toContainText(
    "Keine Rohprojektidee, Partnernamen, Budgets oder Kontaktangaben"
  )
  await expect(panel.getByText("Brief v1 freigegeben")).toBeVisible()

  // Freigegebene Queries ausführen → Ergebnisse klar als «Demo» markiert,
  // ohne «Übernehmen» (Demo-Ergebnisse werden nie zu Quellen).
  await panel.getByRole("button", { name: "Freigegebene Queries ausführen" }).click()
  const results = page.getByTestId("research-results")
  await expect(results.getByText("Demo", { exact: true }).first()).toBeVisible({
    timeout: 30_000,
  })
  await expect(
    results.getByRole("button", { name: "Übernehmen", exact: true })
  ).toHaveCount(0)

  // No provider/API terminology anywhere on the page.
  await expect(page.locator("body")).not.toContainText(/firecrawl/i)

  await page.getByText("Anna Keller").first().click()
  await page.getByText("Abmelden").click()
  await expect(page).toHaveURL(/\/login/, { timeout: 20_000 })
})
