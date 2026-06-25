import { test, expect, type APIRequestContext } from "@playwright/test"

// Milestone 7 deterministic review/recheck/approval end-to-end (no LLM/cloud).
// Drives the contract flow through the BFF/API context and smoke-checks the live
// Review-Center UI (APP_BACKEND_MODE=live, deterministic).
const EMAIL = process.env.E2E_EMAIL ?? "anna.keller@example.test"
const PASSWORD = process.env.E2E_PASSWORD ?? "changeme-dev-lead"
const ORIGIN = "http://localhost:3000"
const CLASSIFICATION = {
  sensitivity: "public",
  origin: "synthetic",
  processing_mode: "deterministic_only",
  web_research_mode: "off",
  nda_applies: false,
}
const SOURCE_TEXT =
  "Der Umsetzungspartner ist in der Schweiz wertschöpfend tätig. " +
  "Ein beitragsberechtigter Schweizer Forschungspartner ist eingebunden."
const ABSTRACT = "INTRO.APP.ABSTRACT"

function idem(): string {
  return Math.random().toString(36).slice(2) + Date.now().toString(36)
}

async function getReview(api: APIRequestContext, runId: string) {
  return (await (await api.get(`/api/runs/${runId}/review`)).json()) as {
    approval_status: string
    recheck_required: boolean
    blocker_count: number
    review_package_version: string
    current_approval_scope_hash: string
    findings: { requirement_id: string | null; severity: string }[]
  }
}

async function completeRun(
  api: APIRequestContext,
  mut: () => Record<string, string>,
  title: string,
  withResearchPartner: boolean
): Promise<{ projectId: string; runId: string }> {
  const projectId = (await (await api.post("/api/projects", {
    headers: mut(),
    data: {
      title,
      description: "Review e2e.",
      funding_instrument_profile_id:
        "innosuisse_innovation_project_with_implementation_partner",
      data_classification: CLASSIFICATION,
    },
  })).json()).project_id as string

  await api.post(`/api/projects/${projectId}/sources/text`, {
    headers: mut(),
    data: { name: "Quelle", text: SOURCE_TEXT, data_classification: CLASSIFICATION },
  })
  const partners: Record<string, unknown>[] = [
    { name: "Industrie AG", partner_type: "implementation_partner", country: "CH", swiss_value_creation: true },
  ]
  if (withResearchPartner) {
    partners.push({
      name: "ETH",
      partner_type: "research_partner",
      country: "CH",
      research_partner_eligibility_status: "eligible",
    })
  }
  for (const partner of partners) {
    await api.post(`/api/projects/${projectId}/partners`, { headers: mut(), data: partner })
  }
  const accepted = await (await api.post(`/api/projects/${projectId}/runs`, {
    headers: mut(),
    data: { settings: { processing_mode: "deterministic_only", max_cost_chf: 0, max_llm_calls: 0, max_web_calls: 0 } },
  })).json()
  let status = ""
  for (let i = 0; i < 40; i++) {
    status = (await (await api.get(`/api/operations/${accepted.operation_id}`)).json()).status
    if (["succeeded", "failed", "cancelled"].includes(status)) break
    await new Promise((r) => setTimeout(r, 300))
  }
  expect(status).toBe("succeeded")
  return { projectId, runId: accepted.resource_id as string }
}

test("M7 review: edit → recheck → field approval → stale; missing partner stays blocked", async ({
  page,
}) => {
  await page.goto("/login")
  await page.getByLabel("E-Mail").fill(EMAIL)
  await page.getByLabel("Passwort").fill(PASSWORD)
  await page.getByRole("button", { name: "Anmelden" }).click()
  await expect(page).toHaveURL(/\/$/, { timeout: 20_000 })

  const api = page.request
  const csrf = (await (await api.get("/api/session")).json()).csrf_token as string
  const mut = () => ({
    "X-CSRF-Token": csrf,
    Origin: ORIGIN,
    "Idempotency-Key": idem(),
    "Content-Type": "application/json",
  })

  // --- Project A: complete deterministic run -------------------------------
  const a = await completeRun(api, mut, "M7 Review A", true)
  const runId = a.runId

  let pkg = await getReview(api, runId)
  expect(pkg.recheck_required).toBe(false)
  expect(pkg.approval_status).toBe("blocked") // template placeholders block
  expect(pkg.blocker_count).toBeGreaterThan(0)

  // Run-scope approval is blocked while placeholders remain.
  const blocked = await api.post(`/api/runs/${runId}/approvals`, {
    headers: mut(),
    data: {
      scope: "run",
      scope_id: runId,
      expected_approval_scope_hash: pkg.current_approval_scope_hash,
      expected_review_package_version: pkg.review_package_version,
      confirm_not_submission_approval: true,
    },
  })
  expect(blocked.status()).toBe(409)
  expect((await blocked.json()).code).toBe("approval_blocked")

  // Edit ABSTRACT to placeholder-free text → recheck required.
  const abstract = (await (await api.get(`/api/runs/${runId}/fields`)).json()).find(
    (f: { field_id: string }) => f.field_id === ABSTRACT
  )
  await api.patch(`/api/runs/${runId}/fields/${ABSTRACT}`, {
    headers: mut(),
    data: { base_version_id: abstract.current_version.draft_version_id, text: "Kurzfassung ohne Platzhalter." },
  })
  pkg = await getReview(api, runId)
  expect(pkg.recheck_required).toBe(true)

  // Targeted recheck clears recheck_required (still blocked elsewhere).
  const recheck = await api.post(`/api/runs/${runId}/rechecks`, {
    headers: mut(),
    data: { expected_review_package_version: pkg.review_package_version, changed_target_refs: [] },
  })
  expect(recheck.status()).toBe(202)
  const opId = (await recheck.json()).operation_id
  let opStatus = ""
  for (let i = 0; i < 40; i++) {
    opStatus = (await (await api.get(`/api/operations/${opId}`)).json()).status
    if (["succeeded", "failed", "cancelled"].includes(opStatus)) break
    await new Promise((r) => setTimeout(r, 300))
  }
  expect(opStatus).toBe("succeeded")
  pkg = await getReview(api, runId)
  expect(pkg.recheck_required).toBe(false)

  // Field-scope approval of the cleaned field succeeds.
  const approve = await api.post(`/api/runs/${runId}/approvals`, {
    headers: mut(),
    data: {
      scope: "field",
      scope_id: ABSTRACT,
      expected_approval_scope_hash: pkg.current_approval_scope_hash,
      expected_review_package_version: pkg.review_package_version,
      confirm_not_submission_approval: true,
    },
  })
  expect(approve.status()).toBe(201)
  expect((await approve.json()).status).toBe("approved")

  // A further edit invalidates the approval (stale) + requires recheck again.
  const fresh = (await (await api.get(`/api/runs/${runId}/fields`)).json()).find(
    (f: { field_id: string }) => f.field_id === ABSTRACT
  )
  await api.patch(`/api/runs/${runId}/fields/${ABSTRACT}`, {
    headers: mut(),
    data: { base_version_id: fresh.current_version.draft_version_id, text: "Aktualisierte Kurzfassung." },
  })
  pkg = await getReview(api, runId)
  expect(pkg.approval_status).toBe("stale")
  expect(pkg.recheck_required).toBe(true)

  // UI smoke: the live Review-Center renders for the active project.
  await page.evaluate((pid) => sessionStorage.setItem("rf_active_project_id", pid), a.projectId)
  await page.goto("/review")
  await expect(page.getByRole("heading", { name: "Review-Center" })).toBeVisible({ timeout: 20_000 })
  await expect(page.getByText(/ungeprüfte Änderungen/)).toBeVisible()

  // --- Project B: missing research partner stays blocked -------------------
  const b = await completeRun(api, mut, "M7 Review B", false)
  const pkgB = await getReview(api, b.runId)
  expect(pkgB.approval_status).toBe("blocked")
  expect(
    pkgB.findings.some(
      (f) => f.severity === "blocker" && f.requirement_id === "REQ.INNO.PARTNER.RESEARCH.MIN1_CH_ELIGIBLE"
    )
  ).toBe(true)

  await page.evaluate((pid) => sessionStorage.setItem("rf_active_project_id", pid), b.projectId)
  await page.goto("/review")
  await expect(page.getByRole("heading", { name: "Review-Center" })).toBeVisible({ timeout: 20_000 })
  await expect(page.getByText("Blockiert")).toBeVisible()
})
