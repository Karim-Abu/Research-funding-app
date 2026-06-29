import { test, expect, type APIRequestContext, type Page } from "@playwright/test"

type Mut = () => Record<string, string>
type RunSettings = Record<string, unknown>

// M9G A3 evidence-consistency review smoke (API context, fake provider).
//
// A targeted recheck on an eligible cloud-assisted (public/synthetic) run runs the
// advisory A3 review and persists ReviewFindings (profile_id A3.evidence_consistency);
// a deterministic-only run's recheck never calls A3. Requires the backend started with
// AGENT_FAKE_PROVIDER=true.
const EMAIL = process.env.E2E_EMAIL ?? "anna.keller@example.test"
const PASSWORD = process.env.E2E_PASSWORD ?? "changeme-dev-lead"
const ORIGIN = "http://localhost:3000"
const A3 = "A3.evidence_consistency"
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

async function projectWithProcessedSource(request: APIRequestContext, mut: Mut): Promise<[string, string]> {
  const projectId = (await (await request.post("/api/projects", {
    headers: mut(),
    data: {
      title: "E2E A3", description: "A3 smoke.",
      funding_instrument_profile_id: "innosuisse_innovation_project_with_implementation_partner",
      data_classification: CLASSIFICATION,
    },
  })).json()).project_id
  await request.post(`/api/projects/${projectId}/sources/text`, {
    headers: mut(),
    data: { name: "Notiz", text: "Synthetic public content for the A3 review smoke.",
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
  return [projectId, sv]
}

async function completedRun(request: APIRequestContext, mut: Mut, projectId: string, settings: RunSettings) {
  const accepted = await (await request.post(`/api/projects/${projectId}/runs`, {
    headers: mut(), data: { settings },
  })).json()
  expect(await waitForOperation(request, accepted.operation_id)).toBe("succeeded")
  return accepted.resource_id as string
}

async function recheck(request: APIRequestContext, mut: Mut, runId: string) {
  const pkg = await (await request.get(`/api/runs/${runId}/review`)).json()
  const res = await request.post(`/api/runs/${runId}/rechecks`, {
    headers: mut(),
    data: { expected_review_package_version: pkg.review_package_version, changed_target_refs: [] },
  })
  expect(res.status()).toBe(202)
  expect(await waitForOperation(request, (await res.json()).operation_id)).toBe("succeeded")
  return (await (await request.get(`/api/runs/${runId}/review`)).json()).findings as
    { profile_id: string; severity: string }[]
}

test("A3 runs on a cloud recheck and persists advisory findings (API context)", async ({ page }) => {
  const mut = await login(page)
  const [projectId, sv] = await projectWithProcessedSource(page.request, mut)
  const confirmationId = (await (await page.request.post(
    `/api/projects/${projectId}/processing-confirmations`,
    { headers: mut(), data: {
      processing_mode: "cloud_assisted", source_version_ids: [sv],
      accepted_policy_version: "1.1.0", purpose: "KI-Prüfung", expires_after_one_run: true } },
  )).json()).confirmation_id
  const runId = await completedRun(page.request, mut, projectId, {
    processing_mode: "cloud_assisted", max_cost_chf: 5, max_llm_calls: 25, max_web_calls: 0,
    source_version_ids: [sv], internal_cloud_confirmation_id: confirmationId,
  })

  const findings = await recheck(page.request, mut, runId)
  expect(findings.some((f) => f.profile_id === A3)).toBe(true)

  await page.getByText("Anna Keller").first().click()
  await page.getByText("Abmelden").click()
  await expect(page).toHaveURL(/\/login/, { timeout: 20_000 })
})

test("deterministic recheck does not run A3 (API context)", async ({ page }) => {
  const mut = await login(page)
  const [projectId, sv] = await projectWithProcessedSource(page.request, mut)
  const runId = await completedRun(page.request, mut, projectId, {
    processing_mode: "deterministic_only", max_cost_chf: 0, max_llm_calls: 0, max_web_calls: 0,
    source_version_ids: [sv],
  })

  const findings = await recheck(page.request, mut, runId)
  expect(findings.some((f) => f.profile_id === A3)).toBe(false)

  await page.getByText("Anna Keller").first().click()
  await page.getByText("Abmelden").click()
  await expect(page).toHaveURL(/\/login/, { timeout: 20_000 })
})
