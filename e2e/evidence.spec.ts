import { test, expect } from "@playwright/test"

// Milestone 5 deterministic evidence end-to-end (no LLM/cloud). Run is driven
// through the BFF/API request context; the live Evidenz workspace is then
// smoke-checked in the real UI (APP_BACKEND_MODE=live, deterministic_only).
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
// Sentences lexically overlap requirement titles so deterministic discovery
// produces verifiable evidence.
const SOURCE_TEXT =
  "Industrie AG ist als Umsetzungspartner in der Schweiz wertschöpfend tätig. " +
  "ETH Zürich ist als beitragsberechtigter Schweizer Forschungspartner eingebunden. " +
  "Das Gesuch ist vollständig und inhaltlich nachvollziehbar ausgefüllt."

function idem(): string {
  return Math.random().toString(36).slice(2) + Date.now().toString(36)
}

test("M5 deterministic evidence end-to-end", async ({ page }) => {
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

  const projectRes = await page.request.post("/api/projects", {
    headers: mut(),
    data: {
      title: "M5 Evidence",
      description: "Deterministic evidence baseline.",
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
      data: { name: "Quelle", text: SOURCE_TEXT, data_classification: CLASSIFICATION },
    }
  )
  const source = await src.json()
  expect(source.status).toBe("processed")
  const selected = await page.request.put(
    `/api/projects/${projectId}/primary-application`,
    {
      headers: mut(),
      data: {
        source_id: source.source_id,
        expected_primary_source_id: null,
      },
    }
  )
  expect(selected.status()).toBe(200)

  for (const partner of [
    { name: "Industrie AG", partner_type: "implementation_partner", country: "CH", swiss_value_creation: true },
    { name: "ETH Zürich", partner_type: "research_partner", country: "CH", research_partner_eligibility_status: "eligible" },
  ]) {
    await page.request.post(`/api/projects/${projectId}/partners`, {
      headers: mut(),
      data: partner,
    })
  }

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

  // Requirement assessments exist; evidence has ≥1 exact_verified anchor.
  const assessments = await (
    await page.request.get(`/api/runs/${accepted.resource_id}/requirements`)
  ).json()
  expect(assessments.length).toBeGreaterThan(0)

  const anchors = await (
    await page.request.get(`/api/runs/${accepted.resource_id}/evidence`)
  ).json()
  const verified = anchors.filter(
    (a: { verification_status: string }) => a.verification_status === "exact_verified"
  )
  expect(verified.length).toBeGreaterThan(0)
  expect(verified[0].quote.length).toBeGreaterThan(0)
  expect(verified[0].match_score).toBeNull()

  // UI smoke: live Evidenz workspace shows a confirmed quote.
  await page.addInitScript((pid) => {
    try {
      window.sessionStorage.setItem("rf_active_project_id", pid as string)
    } catch {
      /* storage may be blocked */
    }
  }, projectId)
  // R6-Statusleiter: eine exakt gefundene Textstelle rendert als
  // "Textstelle gefunden" (Coverage) — nie mehr als grünes "Fundstelle
  // bestätigt" (das bleibt Zusatzinfo in den Details).
  await page.goto("/anforderungen?tab=evidenz")
  await expect(
    page.getByText("Textstelle gefunden – fachliche Prüfung offen").first()
  ).toBeVisible({ timeout: 20_000 })
  // No human-check affordance in M5.
  await expect(page.getByText(/Geprüft von/)).toHaveCount(0)

  // Refresh — evidence persists.
  await page.reload()
  await expect(
    page.getByText("Textstelle gefunden – fachliche Prüfung offen").first()
  ).toBeVisible({ timeout: 20_000 })

  await page.getByText("Anna Keller").first().click()
  await page.getByText("Abmelden").click()
  await expect(page).toHaveURL(/\/login/, { timeout: 20_000 })
})
