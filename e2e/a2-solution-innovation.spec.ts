import { test, expect } from "@playwright/test"

// M9D A2 Solution & Innovation technical smoke (API context).
//
// This evaluation-beta deployment gates cloud-assisted processing off (M3 returns
// 403 cloud_processing_unavailable), so A2 suggestions are deliberately UNAVAILABLE
// here: createRedraft returns a safe 503 ("nicht verfügbar"). This spec verifies
// that safe-unavailable behaviour end-to-end through the live HTTP stack, plus that
// the endpoint is scoped to the Solution & Innovation field. The full
// create→accept→recheck flow (which needs a cloud_assisted run) is covered by the
// backend API tests and the frontend vitest tests.
const EMAIL = process.env.E2E_EMAIL ?? "anna.keller@example.test"
const PASSWORD = process.env.E2E_PASSWORD ?? "changeme-dev-lead"
const ORIGIN = "http://localhost:3000"
const SOL = "SOL.INNOVATION_SOLUTION.EDITOR"
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

test("A2 solution-innovation: safe unavailable + field scope (API context)", async ({
  page,
}) => {
  await page.goto("/login")
  await page.getByLabel("E-Mail").fill(EMAIL)
  await page.getByLabel("Passwort").fill(PASSWORD)
  await page.getByRole("button", { name: "Anmelden" }).click()
  await expect(page).toHaveURL(/\/$/, { timeout: 20_000 })

  const session = await page.request.get("/api/session")
  const csrf = (await session.json()).csrf_token as string
  const mut = () => ({
    "X-CSRF-Token": csrf,
    Origin: ORIGIN,
    "Idempotency-Key": idem(),
    "Content-Type": "application/json",
  })

  const projectId = (
    await (
      await page.request.post("/api/projects", {
        headers: mut(),
        data: {
          title: "E2E A2 Project",
          description: "A2 suggestion smoke.",
          funding_instrument_profile_id:
            "innosuisse_innovation_project_with_implementation_partner",
          data_classification: CLASSIFICATION,
        },
      })
    ).json()
  ).project_id

  await page.request.post(`/api/projects/${projectId}/sources/text`, {
    headers: mut(),
    data: {
      name: "Notiz",
      text: "Synthetic public project content for the A2 smoke.",
      data_classification: CLASSIFICATION,
    },
  })

  const accepted = await (
    await page.request.post(`/api/projects/${projectId}/runs`, {
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
  ).json()
  const runId = accepted.resource_id

  let status = ""
  for (let i = 0; i < 40; i++) {
    const op = await page.request.get(`/api/operations/${accepted.operation_id}`)
    status = (await op.json()).status
    if (["succeeded", "failed", "cancelled"].includes(status)) break
    await page.waitForTimeout(500)
  }
  expect(status).toBe("succeeded")

  // The Solution & Innovation draft exists (M6 template, created_by=template).
  const draft = await (
    await page.request.get(`/api/runs/${runId}/fields/${SOL}`)
  ).json()
  const base = draft.current_version.draft_version_id
  expect(draft.current_version.created_by).toBe("template")

  // createRedraft for SOL on a deterministic-only run → safe 503 (unavailable),
  // never an auto-applied draft change.
  const redraft = await page.request.post(
    `/api/runs/${runId}/fields/${SOL}/redrafts`,
    { headers: mut(), data: { base_version_id: base } }
  )
  expect(redraft.status()).toBe(503)
  expect((await redraft.json()).code).toBe("ai_unavailable")

  // A2 is scoped to the SOL field — any other field 404s (no AI surface there).
  const other = await page.request.post(
    `/api/runs/${runId}/fields/INTRO.APP.ABSTRACT/redrafts`,
    { headers: mut(), data: { base_version_id: base } }
  )
  expect(other.status()).toBe(404)

  // The draft was not mutated by the (unavailable) suggestion request.
  const after = await (
    await page.request.get(`/api/runs/${runId}/fields/${SOL}`)
  ).json()
  expect(after.current_version.draft_version_id).toBe(base)

  await page.getByText("Anna Keller").first().click()
  await page.getByText("Abmelden").click()
  await expect(page).toHaveURL(/\/login/, { timeout: 20_000 })
})
