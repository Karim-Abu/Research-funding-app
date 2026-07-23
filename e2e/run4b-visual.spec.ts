// RUN 4B — visuelle Nachweise (Mandat §13): Screenshots der zentralen
// Schreibassistent-Zustände nach docs/assets/run4b/ bei 1440×900, 1280×800,
// 768×1024 (+ 390×844 als mobiler Zusatznachweis für die gestapelte Ansicht).
// Opt-in und NIE Teil der Gates:
//   RUN4B_VISUAL=1 corepack pnpm exec playwright test e2e/run4b-visual.spec.ts
// Voraussetzungen wie e2e/run4b-editor.spec.ts (lokale Server, Fake-Provider).
// Fixture-Zustände sind IMMER ehrlich als fake_demo gekennzeichnet.
import { mkdirSync } from "node:fs"
import path from "node:path"
import { test, expect, type APIRequestContext, type Page } from "@playwright/test"

const EMAIL = process.env.E2E_EMAIL ?? "anna.keller@example.test"
const PASSWORD = process.env.E2E_PASSWORD ?? "changeme-dev-lead"
const ORIGIN = "http://localhost:3000"
const SOL = "SOL.INNOVATION_SOLUTION.EDITOR"
const VC = "VC.BUSINESS_TARGETS_MODEL.EDITOR"
const OUT_DIR = path.join(process.cwd(), "docs", "assets", "run4b")
const VIEWPORTS = [
  { width: 1440, height: 900 },
  { width: 1280, height: 800 },
  { width: 768, height: 1024 },
]
const CLASSIFICATION = {
  sensitivity: "public",
  origin: "synthetic",
  processing_mode: "deterministic_only",
  web_research_mode: "off",
  nda_applies: false,
}

test.skip(
  process.env.RUN4B_VISUAL !== "1",
  "Set RUN4B_VISUAL=1 to capture the RUN 4B visual evidence screenshots."
)

function idem(): string {
  return Math.random().toString(36).slice(2) + Date.now().toString(36)
}

async function waitOp(request: APIRequestContext, id: string): Promise<string> {
  let status = ""
  for (let i = 0; i < 60; i++) {
    status = (await (await request.get(`/api/operations/${id}`)).json()).status
    if (["succeeded", "failed", "cancelled"].includes(status)) break
    await new Promise((r) => setTimeout(r, 500))
  }
  return status
}

async function shoot(page: Page, name: string, viewports = VIEWPORTS) {
  for (const viewport of viewports) {
    await page.setViewportSize(viewport)
    await page.waitForTimeout(400)
    await page.screenshot({
      path: path.join(OUT_DIR, `${name}-${viewport.width}x${viewport.height}.png`),
      fullPage: true,
    })
  }
}

function suggestionFixture(base: string, extra: Record<string, unknown> = {}) {
  return {
    suggestion: {
      suggestion_id: "vx-s1",
      operation_id: "vx-op1",
      field_id: SOL,
      target_section: "4.2",
      generation_kind: "fake_demo",
      execution_mode: "fake_demo",
      base_version_id: base,
      suggested_text:
        "4.1 Ausgangslage bleibt.\n4.2 Neuheit: klarere Darstellung mit zwei Belegen und offenen Angaben.",
      rationale: "An verfügbare Belege und Anforderungen angepasst.",
      evidence: [
        {
          anchor_id: "vx-a1",
          quote: "Belegte Passage eins.",
          source_name: "Quelle-1.txt",
          verification_status: "exact_verified",
          page: 2,
        },
        {
          anchor_id: "vx-a2",
          quote: "Belegte Passage zwei.",
          source_name: "Quelle-2.txt",
          verification_status: "exact_verified",
          section: "2.1",
        },
      ],
      research_sources: [],
      open_issue_ids: [],
      placeholders: [],
      character_count: 108,
      character_limit: 25000,
      warnings: ["fake_demo_no_model"],
      missing_inputs: [
        {
          key: "swiss_market_size",
          label: "Schweizer Marktgrösse",
          reason: "Ohne belegte Zahl bleibt der Abschnitt unvollständig.",
          requirement_ids: [],
        },
        {
          key: "trl_evidence",
          label: "TRL-Nachweis",
          reason: "Der Reifegrad braucht eine nachvollziehbare Quelle.",
          requirement_ids: [],
        },
      ],
      manifest_id: "vx-manifest",
      accept_mode: "whole_suggestion_only",
      improvement_mode: "complete_innolink_requirements",
      ...extra,
    },
  }
}

test("RUN 4B — Screenshots der Schreibassistent-Zustände", async ({ page }) => {
  test.setTimeout(600_000)
  mkdirSync(OUT_DIR, { recursive: true })

  // Login + Cloud-Projekt + Lauf (Fake-Provider) — Muster run4b-editor.spec.
  await page.goto("/login")
  await page.getByLabel("E-Mail").fill(EMAIL)
  await page.getByLabel("Passwort").fill(PASSWORD)
  await page.getByRole("button", { name: "Anmelden" }).click()
  await expect(page).toHaveURL(/\/$/, { timeout: 20_000 })
  const csrf = (await (await page.request.get("/api/session")).json())
    .csrf_token as string
  const mut = () => ({
    "X-CSRF-Token": csrf,
    Origin: ORIGIN,
    "Idempotency-Key": idem(),
    "Content-Type": "application/json",
  })
  const title = `RUN4B Visual ${idem()}`
  const projectId = (
    await (
      await page.request.post("/api/projects", {
        headers: mut(),
        data: {
          title,
          description: "RUN 4B visuelle Nachweise.",
          funding_instrument_profile_id:
            "innosuisse_innovation_project_with_implementation_partner",
          data_classification: CLASSIFICATION,
        },
      })
    ).json()
  ).project_id as string
  await page.request.post(`/api/projects/${projectId}/sources/text`, {
    headers: mut(),
    data: {
      name: "Notiz",
      text: "Synthetic public project content for the RUN 4B visuals.",
      data_classification: CLASSIFICATION,
    },
  })
  let sourceVersionId = ""
  for (let i = 0; i < 40; i++) {
    const list = (await (
      await page.request.get(`/api/projects/${projectId}/sources`)
    ).json()) as { status: string; current_source_version_id?: string }[]
    const ready = list.find(
      (s) => s.status === "processed" && s.current_source_version_id
    )
    if (ready?.current_source_version_id) {
      sourceVersionId = ready.current_source_version_id
      break
    }
    await page.waitForTimeout(500)
  }
  const confirmation = await page.request.post(
    `/api/projects/${projectId}/processing-confirmations`,
    {
      headers: mut(),
      data: {
        processing_mode: "cloud_assisted",
        source_version_ids: [sourceVersionId],
        accepted_policy_version: "1.1.0",
        purpose: "KI-Vorschläge für Textentwürfe vorbereiten",
        expires_after_one_run: true,
      },
    }
  )
  const confirmationId = (await confirmation.json()).confirmation_id as string
  const accepted = await (
    await page.request.post(`/api/projects/${projectId}/runs`, {
      headers: mut(),
      data: {
        settings: {
          processing_mode: "cloud_assisted",
          max_cost_chf: 5,
          max_llm_calls: 25,
          max_web_calls: 0,
          source_version_ids: [sourceVersionId],
          internal_cloud_confirmation_id: confirmationId,
        },
      },
    })
  ).json()
  expect(await waitOp(page.request, accepted.operation_id)).toBe("succeeded")
  const runId = accepted.resource_id as string
  await page.goto("/")
  await page.getByRole("heading", { name: title }).click()
  await expect(page).not.toHaveURL(/\/$/, { timeout: 20_000 })
  const draft = await (
    await page.request.get(`/api/runs/${runId}/fields/${SOL}`)
  ).json()
  const base = draft.current_version.draft_version_id as string

  // 1) Normaler Vorschlag inkl. Missing Inputs + 2 Belege (ein Sheet-Zustand
  //    deckt die Nachweise «normal», «Missing Inputs» und «2 Belege» ab).
  await page.route(`**/api/runs/${runId}/fields/${SOL}/suggestion*`, (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(suggestionFixture(base)),
    })
  )
  await page.goto(`/editor?field=${SOL}`)
  await page.getByRole("button", { name: "Vorschläge", exact: true }).click()
  await shoot(page, "editor-zweispalten", [
    { width: 1440, height: 900 },
    { width: 768, height: 1024 },
    { width: 390, height: 844 },
  ])
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.getByRole("button", { name: "Vorschlag prüfen" }).click()
  await expect(page.getByTestId("current-text")).toBeVisible({ timeout: 20_000 })
  await page.getByText("Belegdetails anzeigen").click()
  await shoot(page, "vorschlag-mit-belegen-und-missing-inputs")
  await page.keyboard.press("Escape")

  // 2) Stale.
  await page.unroute(`**/api/runs/${runId}/fields/${SOL}/suggestion*`)
  await page.route(`**/api/runs/${runId}/fields/${SOL}/suggestion*`, (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(
        suggestionFixture(base, { stale_reason: "source_version_changed" })
      ),
    })
  )
  await page.goto(`/editor?field=${SOL}`)
  await page.getByRole("button", { name: "Vorschläge", exact: true }).click()
  await page.getByRole("button", { name: "Vorschlag prüfen" }).click()
  await expect(page.getByTestId("suggestion-stale-notice")).toBeVisible({
    timeout: 20_000,
  })
  await shoot(page, "vorschlag-veraltet")
  await page.keyboard.press("Escape")

  // 3) Providerfehler (503) — ehrlich, kein Demo-Fallback.
  await page.unroute(`**/api/runs/${runId}/fields/${SOL}/suggestion*`)
  await page.route(`**/api/runs/${runId}/fields/${SOL}/suggestion*`, (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ suggestion: null }),
    })
  )
  await page.route(`**/api/runs/${runId}/fields/${SOL}/redrafts`, (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({
        code: "ai_unavailable",
        reason_code: "provider_unavailable",
      }),
    })
  )
  await page.goto(`/editor?field=${SOL}`)
  await page.getByRole("button", { name: "Vorschläge", exact: true }).click()
  await page
    .getByTestId("a2-suggestion-control")
    .getByRole("button", {
      name: /Vorschlag erstellen|Demo-Vorschlag erstellen|Text mit KI verbessern/,
    })
    .first()
    .click()
  await expect(
    page.getByText(/kein freigegebener KI-Provider konfiguriert/)
  ).toBeVisible({ timeout: 20_000 })
  await shoot(page, "provider-nicht-verfuegbar")

  // 4) Accepted + neue Version (REAL: echter Fake-Provider-Vorschlag).
  await page.unroute(`**/api/runs/${runId}/fields/${SOL}/suggestion*`)
  await page.unroute(`**/api/runs/${runId}/fields/${SOL}/redrafts`)
  const redraft = await page.request.post(
    `/api/runs/${runId}/fields/${SOL}/redrafts`,
    {
      headers: mut(),
      data: { base_version_id: base, target_section: "4.1" },
    }
  )
  const redraftOp = (await redraft.json()).operation_id as string
  expect(await waitOp(page.request, redraftOp)).toBe("succeeded")
  const suggestion = (
    await (await page.request.get(`/api/operations/${redraftOp}`)).json()
  ).result
  await page.request.post(
    `/api/runs/${runId}/fields/${SOL}/suggestions/${suggestion.suggestion_id}/accept`,
    { headers: mut(), data: { base_version_id: suggestion.base_version_id } }
  )
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto(`/editor?field=${SOL}`)
  await expect(
    page.getByText("Aus KI-Vorschlag übernommen").first()
  ).toBeVisible({ timeout: 20_000 })
  await page.getByRole("button", { name: "Prüfen", exact: true }).click()
  await page.getByRole("tab", { name: "Versionen" }).click()
  await expect(page.getByTestId("version-row").first()).toBeVisible({
    timeout: 20_000,
  })
  await shoot(page, "uebernommen-neue-version")

  // 5) Market limited ohne Items.
  await page.route(
    `**/api/projects/${projectId}/market-comparisons/latest`,
    (route) =>
      route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          comparison_id: "vx-c1",
          project_id: projectId,
          status: "limited",
          comparison_version: 1,
          research_gaps: ["Es fehlen geprüfte Quellen zu Anbietern."],
          warnings: [],
          item_count: 0,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          items: [],
        }),
      })
  )
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto(`/editor?field=${VC}`)
  await page.getByRole("button", { name: "Prüfen", exact: true }).click()
  await page.getByRole("tab", { name: "Markt & Wettbewerb" }).click()
  await expect(page.getByTestId("market-editor-empty")).toBeVisible({
    timeout: 20_000,
  })
  await shoot(page, "markt-limited-ohne-items")
})
