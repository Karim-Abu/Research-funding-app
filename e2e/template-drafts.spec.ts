import { test, expect } from "@playwright/test"

// Milestone 6 deterministic template drafts end-to-end (no LLM/cloud).
// Setup + conflict/link mechanics via the BFF/API context; the live Proposal
// Editor is smoke-checked in the real UI (APP_BACKEND_MODE=live, deterministic).
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

function idem(): string {
  return Math.random().toString(36).slice(2) + Date.now().toString(36)
}

test("M6 template drafts: edit, persist, link, stale, conflict", async ({ page }) => {
  await page.goto("/login")
  await page.getByLabel("E-Mail").fill(EMAIL)
  await page.getByLabel("Passwort").fill(PASSWORD)
  await page.getByRole("button", { name: "Anmelden" }).click()
  await expect(page).toHaveURL(/\/$/, { timeout: 20_000 })

  const csrf = (await (await page.request.get("/api/session")).json()).csrf_token as string
  const mut = () => ({
    "X-CSRF-Token": csrf,
    Origin: ORIGIN,
    "Idempotency-Key": idem(),
    "Content-Type": "application/json",
  })

  const projectId = (await (await page.request.post("/api/projects", {
    headers: mut(),
    data: {
      title: "M6 Drafts",
      description: "Template drafts.",
      funding_instrument_profile_id: "innosuisse_innovation_project_with_implementation_partner",
      data_classification: CLASSIFICATION,
    },
  })).json()).project_id

  await page.request.post(`/api/projects/${projectId}/sources/text`, {
    headers: mut(),
    data: { name: "Quelle", text: SOURCE_TEXT, data_classification: CLASSIFICATION },
  })
  for (const partner of [
    { name: "Industrie AG", partner_type: "implementation_partner", country: "CH", swiss_value_creation: true },
    { name: "ETH", partner_type: "research_partner", country: "CH", research_partner_eligibility_status: "eligible" },
  ]) {
    await page.request.post(`/api/projects/${projectId}/partners`, { headers: mut(), data: partner })
  }
  const accepted = await (await page.request.post(`/api/projects/${projectId}/runs`, {
    headers: mut(),
    data: { settings: { processing_mode: "deterministic_only", max_cost_chf: 0, max_llm_calls: 0, max_web_calls: 0 } },
  })).json()
  let opStatus = ""
  for (let i = 0; i < 40; i++) {
    opStatus = (await (await page.request.get(`/api/operations/${accepted.operation_id}`)).json()).status
    if (["succeeded", "failed", "cancelled"].includes(opStatus)) break
    await page.waitForTimeout(300)
  }
  expect(opStatus).toBe("succeeded")
  const runId = accepted.resource_id as string

  // --- API: drafts exist, conflict + evidence-link staleness ---------------
  const fields = await (await page.request.get(`/api/runs/${runId}/fields`)).json()
  expect(fields.length).toBe(8)
  const abstract = fields.find((f: { field_id: string }) => f.field_id === "INTRO.APP.ABSTRACT")
  const baseV1 = abstract.current_version.draft_version_id
  expect(abstract.current_version.created_by).toBe("template")

  const ok = await page.request.patch(`/api/runs/${runId}/fields/INTRO.APP.ABSTRACT`, {
    headers: mut(),
    data: { base_version_id: baseV1, text: "Kurzfassung über Förderfähigkeit." },
  })
  expect(ok.status()).toBe(200)
  const baseV2 = (await ok.json()).current_version.draft_version_id

  // Stale base → 409, no overwrite.
  const conflict = await page.request.patch(`/api/runs/${runId}/fields/INTRO.APP.ABSTRACT`, {
    headers: mut(),
    data: { base_version_id: baseV1, text: "Sollte nicht durchkommen." },
  })
  expect(conflict.status()).toBe(409)
  const stillV2 = await (await page.request.get(`/api/runs/${runId}/fields/INTRO.APP.ABSTRACT`)).json()
  expect(stillV2.current_version.text).toBe("Kurzfassung über Förderfähigkeit.")

  // Link an anchor to the current version, then edit → link becomes stale.
  const anchorId = (await (await page.request.get(`/api/runs/${runId}/evidence`)).json())
    .find((a: { verification_status: string }) => a.verification_status === "exact_verified").anchor_id
  const link = await (await page.request.post(`/api/runs/${runId}/fields/INTRO.APP.ABSTRACT/evidence-links`, {
    headers: mut(),
    data: { anchor_id: anchorId, base_version_id: baseV2 },
  })).json()
  expect(link.status).toBe("active")
  await page.request.patch(`/api/runs/${runId}/fields/INTRO.APP.ABSTRACT`, {
    headers: mut(),
    data: { base_version_id: baseV2, text: "Erneut bearbeitet." },
  })
  const afterEdit = await (await page.request.get(`/api/runs/${runId}/fields/INTRO.APP.ABSTRACT`)).json()
  const staleLink = afterEdit.evidence_links.find((l: { evidence_link_id: string }) => l.evidence_link_id === link.evidence_link_id)
  expect(staleLink.status).toBe("stale")
  // recheck flag set
  expect((await (await page.request.get(`/api/runs/${runId}`)).json()).recheck_required).toBe(true)

  // --- UI smoke: live editor shows + saves a template draft ----------------
  await page.addInitScript((pid) => {
    try { window.sessionStorage.setItem("rf_active_project_id", pid as string) } catch { /* blocked */ }
  }, projectId)
  await page.goto("/editor")
  await expect(page.getByText("Strukturvorlage").first()).toBeVisible({ timeout: 20_000 })
  // Rich-text toolbar rendered (smoke): the editor is a document, not a form box.
  await expect(page.getByRole("button", { name: "Fett" })).toBeVisible({ timeout: 20_000 })
  // The editor is a Tiptap contenteditable — type real keystrokes so ProseMirror
  // updates its state (fill() can desync a contenteditable).
  const editor = page.getByLabel("Entwurf Application name")
  await editor.click()
  await page.keyboard.press("ControlOrMeta+A")
  await page.keyboard.press("Delete")
  await editor.pressSequentially("Projekt Müller & Söhne über Förderfähigkeit")
  await page.getByRole("button", { name: "Speichern" }).click()
  await expect(page.getByText(/erneute Prüfung ist vor der Freigabe erforderlich/)).toBeVisible({ timeout: 20_000 })

  // Switching fields must not tear down the editor under the toolbar (regression:
  // "Cannot read properties of null (reading 'can')"). The toolbar must survive.
  await page.getByRole("button", { name: "Application Name in English" }).click()
  await expect(page.getByRole("button", { name: "Fett" })).toBeVisible({ timeout: 20_000 })
  await expect(page.getByText(/Cannot read properties of null/)).toHaveCount(0)

  await page.reload()
  await expect(page.getByLabel("Entwurf Application name")).toContainText(
    "Projekt Müller & Söhne über Förderfähigkeit",
    { timeout: 20_000 }
  )

  await page.getByText("Anna Keller").first().click()
  await page.getByText("Abmelden").click()
  await expect(page).toHaveURL(/\/login/, { timeout: 20_000 })
})
