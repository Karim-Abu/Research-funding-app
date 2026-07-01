import { test, expect, type APIRequestContext, type Page } from "@playwright/test"

// M10 acceptance flow — API-driven, unconditional, fake providers only. Builds a completed
// deterministic run, runs the reliability pass, checks requirements/evidence, drives the
// Review Center Quality Summary + Innolink UI, creates all three export types, and asserts
// no raw sensitive data / provider branding is shown. No real Firecrawl/LLM.
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

async function waitOp(request: APIRequestContext, opId: string): Promise<string> {
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
      title: "M10 Acceptance", description: "acceptance.",
      funding_instrument_profile_id: "innosuisse_innovation_project_with_implementation_partner",
      data_classification: CLASSIFICATION,
    },
  })).json()).project_id
  await request.post(`/api/projects/${projectId}/sources/text`, {
    headers: mut(), data: { name: "Notiz",
      text: "Synthetischer öffentlicher Projektinhalt für die M10-Abnahme.",
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
  expect(await waitOp(request, accepted.operation_id)).toBe("succeeded")
  const rel = await (await request.post(`/api/runs/${accepted.resource_id}/reliability`, {
    headers: mut() })).json()
  expect(await waitOp(request, rel.operation_id)).toBe("succeeded")
  return [projectId, accepted.resource_id]
}

test("M10 acceptance: run → reliability → review → exports → Innolink, no raw leaks", async ({ page }) => {
  const mut = await login(page)
  const [projectId, runId] = await completedRun(page.request, mut)

  // Requirements + evidence are present (API).
  const reqs = await (await page.request.get(`/api/runs/${runId}/requirements`)).json()
  expect(Array.isArray(reqs) && reqs.length).toBeGreaterThan(0)
  const anchors = await (await page.request.get(`/api/runs/${runId}/evidence`)).json()
  expect(Array.isArray(anchors)).toBe(true)

  // All three export types succeed + are non-empty; technical evidence carries the
  // reliability summary and leaks no claim_text.
  for (const kind of ["technical_evidence", "docx", "markdown"]) {
    const acc = await (await page.request.post(`/api/runs/${runId}/exports`, {
      headers: mut(), data: { type: kind, force_draft: false } })).json()
    expect(await waitOp(page.request, acc.operation_id)).toBe("succeeded")
    const art = await (await page.request.get(`/api/exports/${acc.resource_id}`)).json()
    const body = await (await page.request.get(`/api/exports/${art.export_id}/download`)).body()
    expect(body.length).toBeGreaterThan(0)
    if (kind === "technical_evidence") {
      const parsed = JSON.parse(body.toString("utf-8"))
      expect(parsed.reliability.available).toBe(true)
      expect(body.toString("utf-8")).not.toContain("claim_text")
    }
  }

  // UI: Review Center shows the Quality Summary; Innolink loads. No provider branding.
  await page.evaluate((id) => sessionStorage.setItem("rf_active_project_id", id), projectId)
  await page.goto("/review")
  await expect(page.getByTestId("quality-summary")).toBeVisible({ timeout: 20_000 })
  await expect(page.locator("body")).not.toContainText(/firecrawl|anthropic|haiku/i)

  await page.goto("/editor")
  await expect(page).toHaveURL(/\/editor/)

  await page.goto("/portal-transfer")
  await expect(page.locator("body")).not.toContainText(/firecrawl|anthropic|haiku/i)

  await page.getByText("Anna Keller").first().click()
  await page.getByText("Abmelden").click()
  await expect(page).toHaveURL(/\/login/, { timeout: 20_000 })
})
