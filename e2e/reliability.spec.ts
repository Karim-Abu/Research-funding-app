import { test, expect, type APIRequestContext, type Page } from "@playwright/test"

// M9K MAS reliability & value assurance smoke (API + UI, deterministic — no provider).
// Requires the backend started with AGENT_FAKE_PROVIDER=true (the pass itself makes no
// provider call). Runs a reliability pass on a completed run, checks the RunQualitySummary,
// confirms no draft is mutated, and that the technical-evidence export carries the summary
// without claim_text.
type Mut = () => Record<string, string>

const EMAIL = process.env.E2E_EMAIL ?? "anna.keller@example.test"
const PASSWORD = process.env.E2E_PASSWORD ?? "changeme-dev-lead"
const ORIGIN = "http://localhost:3000"
const CLASSIFICATION = {
  sensitivity: "public", origin: "synthetic", processing_mode: "deterministic_only",
  web_research_mode: "off", nda_applies: false,
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

async function completedRun(request: APIRequestContext, mut: Mut): Promise<[string, string]> {
  const projectId = (await (await request.post("/api/projects", {
    headers: mut(), data: {
      title: "E2E Reliability", description: "Reliability smoke.",
      funding_instrument_profile_id: "innosuisse_innovation_project_with_implementation_partner",
      data_classification: CLASSIFICATION,
    },
  })).json()).project_id
  await request.post(`/api/projects/${projectId}/sources/text`, {
    headers: mut(), data: { name: "Notiz",
      text: "Synthetischer öffentlicher Projektinhalt für die Zuverlässigkeitsprüfung.",
      data_classification: CLASSIFICATION },
  })
  let sv = ""
  for (let i = 0; i < 40; i++) {
    const list = (await (await request.get(`/api/projects/${projectId}/sources`)).json()) as
      { status: string; current_source_version_id?: string }[]
    const ready = list.find((s) => s.status === "processed" && s.current_source_version_id)
    if (ready?.current_source_version_id) { sv = ready.current_source_version_id; break }
    await new Promise((r) => setTimeout(r, 500))
  }
  expect(sv).not.toBe("")
  const accepted = await (await request.post(`/api/projects/${projectId}/runs`, {
    headers: mut(), data: { settings: {
      processing_mode: "deterministic_only", max_cost_chf: 0, max_llm_calls: 0,
      max_web_calls: 0, source_version_ids: [sv] } },
  })).json()
  expect(await waitForOperation(request, accepted.operation_id)).toBe("succeeded")
  return [projectId, accepted.resource_id as string]
}

async function draftVersionIds(request: APIRequestContext, runId: string): Promise<string[]> {
  const pkg = await (await request.get(`/api/runs/${runId}/review`)).json()
  return (pkg.fields as { current_version_id?: string }[])
    .map((f) => f.current_version_id ?? "").sort((a, b) => a.localeCompare(b))
}

test("reliability pass: summary, no draft mutation, export carries the summary", async ({ page }) => {
  const mut = await login(page)
  const [, runId] = await completedRun(page.request, mut)
  const before = await draftVersionIds(page.request, runId)

  const accepted = await (await page.request.post(
    `/api/runs/${runId}/reliability`, { headers: mut() })).json()
  expect(await waitForOperation(page.request, accepted.operation_id)).toBe("succeeded")

  const view = await (await page.request.get(`/api/runs/${runId}/reliability`)).json()
  expect(view.available).toBe(true)
  expect(view.summary).toBeTruthy()
  expect(typeof view.summary.claim_count).toBe("number")
  expect(view.summary.quality_flag).toMatch(/ok|risky/)

  // No draft was mutated by the reliability pass.
  const after = await draftVersionIds(page.request, runId)
  expect(after).toEqual(before)

  // Technical-evidence export carries the reliability summary, without claim_text.
  const exp = await (await page.request.post(`/api/runs/${runId}/exports`, {
    headers: mut(), data: { type: "technical_evidence", force_draft: false },
  })).json()
  expect(await waitForOperation(page.request, exp.operation_id)).toBe("succeeded")
  const artifact = await (await page.request.get(`/api/exports/${exp.resource_id}`)).json()
  const body = (await (await page.request.get(
    `/api/exports/${artifact.export_id}/download`)).body()).toString("utf-8")
  const parsed = JSON.parse(body)
  expect(parsed.reliability.available).toBe(true)
  expect(parsed.reliability.quality_summary.summary_version).toBeTruthy()
  // The per-claim lineage rows carry only claim_hash + status metadata — never claim text.
  for (const row of parsed.reliability.claim_lineage_summary ?? []) {
    expect(row).toHaveProperty("claim_hash")
    expect(row).not.toHaveProperty("claim_text")
  }

  await page.getByText("Anna Keller").first().click()
  await page.getByText("Abmelden").click()
  await expect(page).toHaveURL(/\/login/, { timeout: 20_000 })
})

test("reliability UI: Quality Summary renders in the Review Center", async ({ page }) => {
  const mut = await login(page)
  const [projectId, runId] = await completedRun(page.request, mut)
  const accepted = await (await page.request.post(
    `/api/runs/${runId}/reliability`, { headers: mut() })).json()
  expect(await waitForOperation(page.request, accepted.operation_id)).toBe("succeeded")

  await page.goto("/")
  await page.evaluate((id) => sessionStorage.setItem("rf_active_project_id", id), projectId)
  await page.goto("/review")
  const card = page.getByTestId("quality-summary")
  await expect(card).toBeVisible({ timeout: 20_000 })
  await expect(card).toContainText("Qualitätsübersicht")
  await expect(page.getByTestId("quality-metrics")).toBeVisible()
  // No provider/model branding anywhere on the page.
  await expect(page.locator("body")).not.toContainText(/firecrawl|anthropic|haiku/i)

  await page.getByText("Anna Keller").first().click()
  await page.getByText("Abmelden").click()
  await expect(page).toHaveURL(/\/login/, { timeout: 20_000 })
})
