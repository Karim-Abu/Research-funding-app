import { test, expect } from "@playwright/test"

// Milestone 4 end-to-end: partner eligibility → run → live RequirementAssessments.
// The run is driven through the BFF/API request context (deterministic, robust);
// the live requirements workspace + partner management are then smoke-checked in
// the real UI (APP_BACKEND_MODE=live).
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

function idem(): string {
  return Math.random().toString(36).slice(2) + Date.now().toString(36)
}

test("M4 requirements & rules precheck end-to-end", async ({ page }) => {
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

  // Project + processed source.
  const projectRes = await page.request.post("/api/projects", {
    headers: mut(),
    data: {
      title: "M4 E2E",
      description: "Requirements precheck.",
      funding_instrument_profile_id:
        "innosuisse_innovation_project_with_implementation_partner",
      data_classification: CLASSIFICATION,
    },
  })
  expect(projectRes.status()).toBe(201)
  const projectId = (await projectRes.json()).project_id

  const src = await page.request.post(
    `/api/projects/${projectId}/sources/text`,
    {
      headers: mut(),
      data: {
        name: "Notiz",
        text: "Source content for the run.",
        data_classification: CLASSIFICATION,
      },
    }
  )
  expect((await src.json()).status).toBe("processed")

  // Eligible partners → the partner rules should pass at machine level.
  await page.request.post(`/api/projects/${projectId}/partners`, {
    headers: mut(),
    data: {
      name: "Industrie AG",
      partner_type: "implementation_partner",
      country: "CH",
      swiss_value_creation: true,
    },
  })
  await page.request.post(`/api/projects/${projectId}/partners`, {
    headers: mut(),
    data: {
      name: "ETH Zürich",
      partner_type: "research_partner",
      country: "CH",
      research_partner_eligibility_status: "eligible",
    },
  })

  // Start run → 202 → poll to succeeded.
  const runRes = await page.request.post(`/api/projects/${projectId}/runs`, {
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
  expect(runRes.status()).toBe(202)
  const accepted = await runRes.json()

  let opStatus = ""
  for (let i = 0; i < 40; i++) {
    const op = await page.request.get(`/api/operations/${accepted.operation_id}`)
    opStatus = (await op.json()).status
    if (["succeeded", "failed", "cancelled"].includes(opStatus)) break
    await page.waitForTimeout(300)
  }
  expect(opStatus).toBe("succeeded")

  // Requirement assessments are produced deterministically.
  const reqRes = await page.request.get(
    `/api/runs/${accepted.resource_id}/requirements`
  )
  expect(reqRes.status()).toBe(200)
  const assessments = (await reqRes.json()) as Array<{
    requirement_id: string
    status: string
    stale: boolean
    review_status?: string
  }>
  const byId = Object.fromEntries(assessments.map((a) => [a.requirement_id, a]))
  // RUN 2A Slice 1: maschinell bestanden + hybrid ⇒ fulfilled; die offene
  // menschliche Bestätigung ist die separate Dimension review_status.
  expect(byId["REQ.INNO.PARTNER.IMPLEMENTATION.MIN1_CH"].status).toBe("fulfilled")
  expect(byId["REQ.INNO.PARTNER.IMPLEMENTATION.MIN1_CH"].review_status).toBe("required")
  expect(byId["REQ.INNO.PARTNER.RESEARCH.MIN1_CH_ELIGIBLE"].status).toBe("fulfilled")
  expect(byId["REQ.INNO.PARTNER.RESEARCH.MIN1_CH_ELIGIBLE"].review_status).toBe("required")
  expect(byId["REQ.INNO.BUDGET.CASH_MIN5"].status).toBe("needs_input")
  for (const a of assessments) {
    expect(["fulfilled", "partial", "open", "needs_input", "blocked"]).toContain(
      a.status
    )
    expect(a.stale).toBe(false)
  }

  // Changing inputs after the snapshot marks the assessments stale.
  await page.request.post(`/api/projects/${projectId}/partners`, {
    headers: mut(),
    data: {
      name: "Weiterer Partner",
      partner_type: "research_partner",
      country: "CH",
      research_partner_eligibility_status: "eligible",
    },
  })
  const stale = (await (
    await page.request.get(`/api/runs/${accepted.resource_id}/requirements`)
  ).json()) as Array<{ stale: boolean }>
  expect(stale.every((a) => a.stale === true)).toBe(true)

  // UI smoke: live requirements workspace renders with status labels.
  await page.addInitScript((pid) => {
    try {
      window.sessionStorage.setItem("rf_active_project_id", pid as string)
    } catch {
      /* storage may be blocked */
    }
  }, projectId)
  await page.goto("/anforderungen")
  await expect(page.getByText("Fördervoraussetzungen").first()).toBeVisible({
    timeout: 20_000,
  })
  await expect(
    page.getByText(/Teilweise|Blockiert|Angaben nötig|Erfüllt|Offen/).first()
  ).toBeVisible()

  // UI smoke: partner management lists the created partners (Slice 1: the
  // page is the "Partner & Budget" workflow step).
  await page.goto("/partner")
  await expect(page.getByText("Partner & Budget").first()).toBeVisible()
  await expect(page.getByText("ETH Zürich").first()).toBeVisible()

  await page.getByText("Anna Keller").first().click()
  await page.getByText("Abmelden").click()
  await expect(page).toHaveURL(/\/login/, { timeout: 20_000 })
})
