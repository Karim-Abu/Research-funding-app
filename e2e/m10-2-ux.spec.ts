import { test, expect, type APIRequestContext } from "@playwright/test"

// M10.2 — evaluation UX polish, deterministic (no provider, no real key):
// dashboard search/filter with an extra user-created project, evidence → source
// navigation, requirement guidance CTA, review "Nächste Schritte", export
// field-readiness overview, and no provider branding in the primary UI.
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
const TITLE = "Eigener Testantrag M10-2 UX"

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

test("M10.2: orientation, links and readiness across the core screens", async ({
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

  // A user-created project is normal — not DB pollution. Build it end to end.
  const projectId = (await (await api.post("/api/projects", {
    headers: mut(),
    data: {
      title: TITLE,
      description: "M10.2 UX e2e.",
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

  // --- Dashboard: search finds the user project; card shows the next step ---
  await page.goto("/")
  const search = page.getByLabel("Anträge durchsuchen")
  await expect(search).toBeVisible({ timeout: 20_000 })
  await search.fill("M10-2 UX")
  await expect(page.getByText(TITLE)).toBeVisible()
  await expect(page.getByText(/Nächster Schritt:/).first()).toBeVisible()
  // Status filter chips exist (orientation instead of pollution warnings).
  await expect(page.getByRole("button", { name: "Alle" })).toBeVisible()

  // Activate this Antrag for the project-scoped screens.
  await page.evaluate((pid) => sessionStorage.setItem("rf_active_project_id", pid), projectId)

  // --- Evidence → source navigation -----------------------------------------
  await page.goto("/anforderungen?tab=evidenz")
  const sourceButton = page
    .getByRole("button", { name: /Quelle „Quelle“ anzeigen/ })
    .first()
  await expect(sourceButton).toBeVisible({ timeout: 20_000 })
  // The explainer separates "found in source" from fachliche Freigabe
  // (R6-Statusleiter: Coverage ≠ Correctness, Bewertung bleibt beim Menschen).
  await expect(
    page.getByText(/abschliessende Bewertung bleibt bei Ihnen/)
  ).toBeVisible()
  await sourceButton.click()
  await expect(page.getByRole("heading", { name: "Quelldetails" })).toBeVisible()
  await page.getByRole("button", { name: "Schließen" }).click()

  // --- Requirements: guidance CTA -------------------------------------------
  await page.goto("/anforderungen")
  await expect(
    page.getByRole("heading", { name: /Anforderungen & Fördervoraussetzungen/ })
  ).toBeVisible({ timeout: 20_000 })
  // Expand the first requirement row and expect a guidance action. The neutral
  // fallback CTA is present unless the primary action already covers it; the
  // Systembefund label separates system finding from human decision.
  const firstRow = page
    .locator('div[id^="req-"] > button[aria-expanded="false"]')
    .first()
  await firstRow.click()
  await expect(page.getByText("Systembefund").first()).toBeVisible()
  await expect(page.getByText(/Warum relevant\?/).first()).toBeVisible()

  // --- Review: Nächste Schritte/Aufgaben -------------------------------------
  await page.goto("/review")
  await expect(
    page.getByRole("heading", { name: "Qualitätsprüfung", exact: true })
  ).toBeVisible({ timeout: 20_000 })
  // Seit R2.5 zeigt der Screen bei offenen Findings die priorisierte Fix
  // Queue («Nächste Aufgaben», fix-queue-next); ohne Gruppen bleibt die alte
  // Ableitung («Nächste Schritte», next-steps) als Fallback.
  const guidance = page
    .getByTestId("fix-queue-next")
    .or(page.getByTestId("next-steps"))
    .first()
  await expect(guidance).toBeVisible({ timeout: 20_000 })
  await expect(guidance).toContainText(/Nächste (Aufgaben|Schritte)/)

  // --- Export: field readiness + honest semantics ----------------------------
  await page.goto("/export")
  await expect(page.getByTestId("field-readiness")).toBeVisible({ timeout: 20_000 })
  await expect(page.getByTestId("field-readiness")).toContainText("Feld-Bereitschaft")
  await expect(page.getByTestId("field-readiness")).toContainText(
    /keine fachliche Freigabe/
  )
  await expect(page.getByText("Nicht zur Einreichung").first()).toBeVisible()
  await expect(page.getByText("Für Audit/Evaluation")).toBeVisible()

  // No provider/model branding anywhere on the primary export surface.
  const body = await page.locator("body").innerText()
  expect(body).not.toMatch(/anthropic|openai|firecrawl|claude|gpt/i)
})
