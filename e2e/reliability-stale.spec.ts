import { test, expect, type APIRequestContext } from "@playwright/test"

// M10.1 (audit F3) — stale reliability governs approval, deterministic (no provider):
// reliability pass → draft edit → recheck → the Review Center shows the stale warning and
// approval is blocked with a reliability_stale reason; a fresh pass resolves the state.
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
const RELIABILITY_PROFILE = "M9K.reliability_assurance"

function idem(): string {
  return Math.random().toString(36).slice(2) + Date.now().toString(36)
}

async function waitOp(api: APIRequestContext, operationId: string): Promise<string> {
  let status = ""
  for (let i = 0; i < 40; i++) {
    status = (await (await api.get(`/api/operations/${operationId}`)).json()).status
    if (["succeeded", "failed", "cancelled"].includes(status)) break
    await new Promise((r) => setTimeout(r, 300))
  }
  return status
}

async function getReview(api: APIRequestContext, runId: string) {
  return (await (await api.get(`/api/runs/${runId}/review`)).json()) as {
    approval_status: string
    review_package_version: string
    current_approval_scope_hash: string
    findings: { profile_id: string; field_id: string | null; severity: string; status: string }[]
  }
}

async function editAbstract(
  api: APIRequestContext,
  mut: () => Record<string, string>,
  runId: string,
  text: string
) {
  const field = (await (await api.get(`/api/runs/${runId}/fields`)).json()).find(
    (f: { field_id: string }) => f.field_id === ABSTRACT
  )
  await api.patch(`/api/runs/${runId}/fields/${ABSTRACT}`, {
    headers: mut(),
    data: { base_version_id: field.current_version.draft_version_id, text },
  })
}

async function recheck(
  api: APIRequestContext,
  mut: () => Record<string, string>,
  runId: string
) {
  const pkg = await getReview(api, runId)
  const res = await api.post(`/api/runs/${runId}/rechecks`, {
    headers: mut(),
    data: { expected_review_package_version: pkg.review_package_version, changed_target_refs: [] },
  })
  expect(res.status()).toBe(202)
  expect(await waitOp(api, (await res.json()).operation_id)).toBe("succeeded")
}

function staleFindings(pkg: Awaited<ReturnType<typeof getReview>>) {
  return pkg.findings.filter(
    (f) => f.profile_id === RELIABILITY_PROFILE && f.field_id === null && f.status === "open"
  )
}

test("M10.1: stale reliability shows in the Review Center and blocks approval", async ({
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

  // Completed deterministic run with a strong unsupported claim in the abstract.
  const projectId = (await (await api.post("/api/projects", {
    headers: mut(),
    data: {
      title: "M10.1 Stale Reliability",
      description: "Stale-reliability e2e.",
      funding_instrument_profile_id:
        "innosuisse_innovation_project_with_implementation_partner",
      data_classification: CLASSIFICATION,
    },
  })).json()).project_id as string
  await api.post(`/api/projects/${projectId}/sources/text`, {
    headers: mut(),
    data: { name: "Quelle", text: SOURCE_TEXT, data_classification: CLASSIFICATION },
  })
  for (const partner of [
    { name: "Industrie AG", partner_type: "implementation_partner", country: "CH", swiss_value_creation: true },
    { name: "ETH", partner_type: "research_partner", country: "CH", research_partner_eligibility_status: "eligible" },
  ]) {
    await api.post(`/api/projects/${projectId}/partners`, { headers: mut(), data: partner })
  }
  const accepted = await (await api.post(`/api/projects/${projectId}/runs`, {
    headers: mut(),
    data: { settings: { processing_mode: "deterministic_only", max_cost_chf: 0, max_llm_calls: 0, max_web_calls: 0 } },
  })).json()
  expect(await waitOp(api, accepted.operation_id)).toBe("succeeded")
  const runId = accepted.resource_id as string

  await editAbstract(api, mut, runId,
    "Wir sind der weltweit erste Anbieter im Markt der Kunden.")
  await recheck(api, mut, runId)

  // Reliability pass on the current draft — nothing stale yet.
  const pass1 = await (await api.post(`/api/runs/${runId}/reliability`, { headers: mut() })).json()
  expect(await waitOp(api, pass1.operation_id)).toBe("succeeded")
  expect(staleFindings(await getReview(api, runId)).length).toBe(0)

  // Draft edit + deterministic recheck → the stale blocker finding appears.
  await editAbstract(api, mut, runId,
    "Wir sind der weltweit erste Anbieter im Markt der neuen Kunden.")
  await recheck(api, mut, runId)
  let pkg = await getReview(api, runId)
  expect(staleFindings(pkg).length).toBe(1)
  expect(pkg.approval_status).toBe("blocked")

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
  const problem = await blocked.json()
  expect(problem.code).toBe("approval_blocked")
  expect(problem.detail).toContain("reliability_stale")

  // Review Center shows the stale warning (normal review path, not the reliability view).
  await page.evaluate((pid) => sessionStorage.setItem("rf_active_project_id", pid), projectId)
  await page.goto("/review")
  await expect(
    page.getByRole("heading", { name: "Qualitätsprüfung", exact: true })
  ).toBeVisible({ timeout: 20_000 })
  await expect(page.getByTestId("reliability-stale-banner")).toBeVisible()
  await expect(page.getByTestId("reliability-stale-banner")).toContainText(
    "Qualitätsprüfung veraltet"
  )

  // A fresh pass resolves the stale state; the banner disappears.
  const pass2 = await (await api.post(`/api/runs/${runId}/reliability`, { headers: mut() })).json()
  expect(await waitOp(api, pass2.operation_id)).toBe("succeeded")
  pkg = await getReview(api, runId)
  expect(staleFindings(pkg).length).toBe(0)
  await page.reload()
  await expect(
    page.getByRole("heading", { name: "Qualitätsprüfung", exact: true })
  ).toBeVisible({ timeout: 20_000 })
  await expect(page.getByTestId("reliability-stale-banner")).toHaveCount(0)
})
