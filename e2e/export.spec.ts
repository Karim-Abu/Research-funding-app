import { test, expect, type APIRequestContext } from "@playwright/test"

// Milestone 8 deterministic export end-to-end (no LLM/cloud/portal submission).
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
const SUPPORTED_FIELDS = [
  "INTRO.APP.NAME",
  "INTRO.APP.NAME_EN",
  "INTRO.APP.ABSTRACT",
  "INTRO.APP.EXECUTIVE_SUMMARY",
  "ORG.INDEPENDENCE.FINANCIAL.EXPLANATIONS_COMMENTS",
  "VC.BUSINESS_TARGETS_MODEL.EDITOR",
  "SOL.INNOVATION_SOLUTION.EDITOR",
  "PS.PLANNED_HOURS.MANAGEMENT_EXPLANATION",
]

function idem(): string {
  return Math.random().toString(36).slice(2) + Date.now().toString(36)
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
      description: "Export e2e.",
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
    partners.push({ name: "ETH", partner_type: "research_partner", country: "CH", research_partner_eligibility_status: "eligible" })
  }
  for (const partner of partners) {
    await api.post(`/api/projects/${projectId}/partners`, { headers: mut(), data: partner })
  }
  const accepted = await (await api.post(`/api/projects/${projectId}/runs`, {
    headers: mut(),
    data: { settings: { processing_mode: "deterministic_only", max_cost_chf: 0, max_llm_calls: 0, max_web_calls: 0 } },
  })).json()
  await pollOp(api, accepted.operation_id)
  return { projectId, runId: accepted.resource_id as string }
}

async function pollOp(api: APIRequestContext, operationId: string): Promise<string> {
  let status = ""
  for (let i = 0; i < 50; i++) {
    status = (await (await api.get(`/api/operations/${operationId}`)).json()).status
    if (["succeeded", "failed", "cancelled"].includes(status)) break
    await new Promise((r) => setTimeout(r, 300))
  }
  expect(status).toBe("succeeded")
  return status
}

async function createExport(
  api: APIRequestContext,
  mut: () => Record<string, string>,
  runId: string,
  type: string
) {
  const accepted = await (await api.post(`/api/runs/${runId}/exports`, {
    headers: mut(),
    data: { type, force_draft: false },
  })).json()
  await pollOp(api, accepted.operation_id)
  return (await (await api.get(`/api/exports/${accepted.resource_id}`)).json())
}

test("M8 export: draft (ENTWURF) flow and approved flow", async ({ page }) => {
  await page.goto("/login")
  await page.getByLabel("E-Mail").fill(EMAIL)
  await page.getByLabel("Passwort").fill(PASSWORD)
  await page.getByRole("button", { name: "Anmelden" }).click()
  await expect(page).toHaveURL(/\/$/, { timeout: 20_000 })

  const api = page.request
  const csrf = (await (await api.get("/api/session")).json()).csrf_token as string
  const mut = () => ({
    "X-CSRF-Token": csrf, Origin: ORIGIN, "Idempotency-Key": idem(),
    "Content-Type": "application/json",
  })

  // --- Draft flow: unapproved run → ENTWURF exports ------------------------
  const draftRun = await completeRun(api, mut, "M8 Export Draft", false)
  const docx = await createExport(api, mut, draftRun.runId, "docx")
  expect(docx.status).toBe("available")
  expect(docx.draft_marked).toBe(true)
  expect(docx.filename).toContain("ENTWURF")

  const dl = await api.get(`/api/exports/${docx.export_id}/download`)
  expect(dl.status()).toBe(200)
  expect(dl.headers()["content-disposition"]).toContain("ENTWURF")
  expect((await dl.body()).slice(0, 2).toString()).toBe("PK")  // docx is a zip

  const tech = await createExport(api, mut, draftRun.runId, "technical_evidence")
  const techBody = JSON.parse(
    (await (await api.get(`/api/exports/${tech.export_id}/download`)).body()).toString("utf-8")
  )
  expect(techBody.draft_marked).toBe(true)
  expect(techBody.artifact_kind).toBe("internal_audit_export")

  // --- Approved flow: all fields filled → recheck → approve → non-draft ----
  const appRun = await completeRun(api, mut, "M8 Export Approved", true)
  for (const fieldId of SUPPORTED_FIELDS) {
    const draft = await (await api.get(`/api/runs/${appRun.runId}/fields/${fieldId}`)).json()
    await api.patch(`/api/runs/${appRun.runId}/fields/${fieldId}`, {
      headers: { "X-CSRF-Token": csrf, Origin: ORIGIN, "Content-Type": "application/json" },
      data: { base_version_id: draft.current_version.draft_version_id, text: "Inhalt fachlich ergänzt." },
    })
  }
  const pkg = await (await api.get(`/api/runs/${appRun.runId}/review`)).json()
  const recheck = await api.post(`/api/runs/${appRun.runId}/rechecks`, {
    headers: mut(),
    data: { expected_review_package_version: pkg.review_package_version, changed_target_refs: [] },
  })
  await pollOp(api, (await recheck.json()).operation_id)
  const pkg2 = await (await api.get(`/api/runs/${appRun.runId}/review`)).json()
  const approval = await api.post(`/api/runs/${appRun.runId}/approvals`, {
    headers: mut(),
    data: {
      scope: "run", scope_id: appRun.runId,
      expected_approval_scope_hash: pkg2.current_approval_scope_hash,
      expected_review_package_version: pkg2.review_package_version,
      confirm_not_submission_approval: true,
    },
  })
  expect(approval.status()).toBe(201)

  const md = await createExport(api, mut, appRun.runId, "markdown")
  expect(md.draft_marked).toBe(false)
  expect(md.filename).not.toContain("ENTWURF")
  const mdText = (await (await api.get(`/api/exports/${md.export_id}/download`)).body()).toString("utf-8")
  expect(mdText).toContain("Dies ist keine Einreichfreigabe")
  expect(mdText).not.toContain("ENTWURF")

  // --- UI smoke: live Export Center ----------------------------------------
  await page.evaluate((pid) => sessionStorage.setItem("rf_active_project_id", pid), draftRun.projectId)
  await page.goto("/export")
  await expect(page.getByRole("heading", { name: "Export" })).toBeVisible({ timeout: 20_000 })
  await expect(page.getByText("Word-Arbeitsdokument")).toBeVisible()
  await expect(page.getByText(/Diese Plattform reicht nichts automatisch ein/)).toBeVisible()
})
