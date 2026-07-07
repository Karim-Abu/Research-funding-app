import { test, expect, type APIRequestContext } from "@playwright/test"

// R1.3 — Status-Paritätstest (dauerhaftes Merge-Gate ab R1).
// Ein Projekt mit X offenen Blockern zeigt exakt X auf allen vier Screens:
// Dashboard, Anforderungen, Qualitätsprüfung, Export — Quelle ist der
// kanonische Status-View (GET /api/runs/{id}/review/status).
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
const TITLE = `R1 Paritätstest ${Date.now()}`

function idem(): string {
  return Math.random().toString(36).slice(2) + Date.now().toString(36)
}

async function completeRun(
  api: APIRequestContext,
  mut: () => Record<string, string>
): Promise<{ projectId: string; runId: string }> {
  const projectId = (await (
    await api.post("/api/projects", {
      headers: mut(),
      data: {
        title: TITLE,
        description: "Status-Paritätstest R1.3.",
        funding_instrument_profile_id:
          "innosuisse_innovation_project_with_implementation_partner",
        data_classification: CLASSIFICATION,
      },
    })
  ).json()).project_id as string

  await api.post(`/api/projects/${projectId}/sources/text`, {
    headers: mut(),
    data: {
      name: "Quelle",
      text: SOURCE_TEXT,
      data_classification: CLASSIFICATION,
    },
  })
  for (const partner of [
    {
      name: "Industrie AG",
      partner_type: "implementation_partner",
      country: "CH",
      swiss_value_creation: true,
    },
    {
      name: "ETH",
      partner_type: "research_partner",
      country: "CH",
      research_partner_eligibility_status: "eligible",
    },
  ]) {
    await api.post(`/api/projects/${projectId}/partners`, {
      headers: mut(),
      data: partner,
    })
  }
  const accepted = await (
    await api.post(`/api/projects/${projectId}/runs`, {
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
  let status = ""
  for (let i = 0; i < 40; i++) {
    status = (
      await (await api.get(`/api/operations/${accepted.operation_id}`)).json()
    ).status
    if (["succeeded", "failed", "cancelled"].includes(status)) break
    await new Promise((r) => setTimeout(r, 300))
  }
  expect(status).toBe("succeeded")
  return { projectId, runId: accepted.resource_id as string }
}

test("R1 Parität: X Blocker identisch auf Dashboard, Anforderungen, Prüfung, Export", async ({
  page,
}) => {
  await page.goto("/login")
  await page.getByLabel("E-Mail").fill(EMAIL)
  await page.getByLabel("Passwort").fill(PASSWORD)
  await page.getByRole("button", { name: "Anmelden" }).click()
  await expect(page).toHaveURL(/\/$/, { timeout: 20_000 })

  const api = page.request
  const csrf = (await (await api.get("/api/session")).json())
    .csrf_token as string
  const mut = () => ({
    "X-CSRF-Token": csrf,
    Origin: ORIGIN,
    "Idempotency-Key": idem(),
    "Content-Type": "application/json",
  })

  const { projectId, runId } = await completeRun(api, mut)

  // Kanonische Referenzzahl X aus dem Status-View.
  const canonical = await (
    await api.get(`/api/runs/${runId}/review/status`)
  ).json()
  const x = canonical.blocker_count as number
  expect(x).toBeGreaterThan(0) // Template-Platzhalter blockieren
  expect(canonical.stale).toBe(false)

  // --- Screen 1: Dashboard — Projektkarte zeigt X --------------------------
  await page.goto("/")
  const card = page
    .locator("div", { has: page.getByRole("heading", { name: TITLE }) })
    .locator('[data-testid="card-blocker-count"]')
    .first()
  await expect(card).toHaveAttribute("data-blocker-count", String(x), {
    timeout: 20_000,
  })
  await expect(card).toHaveText(`${x} Blocker offen`)

  // Aktives Projekt setzen (wie der Karten-Klick), dann die Run-Screens prüfen.
  await page.evaluate(
    (id) => sessionStorage.setItem("rf_active_project_id", id),
    projectId
  )

  // --- Screens 2–4: Anforderungen, Qualitätsprüfung, Export ----------------
  for (const path of ["/anforderungen", "/review", "/export"]) {
    await page.goto(path)
    const badge = page.getByTestId("canonical-blocker-count").first()
    await expect(badge, `Screen ${path} zeigt die kanonische Zahl`).toHaveAttribute(
      "data-blocker-count",
      String(x),
      { timeout: 20_000 }
    )
    await expect(badge).toHaveText(`${x} Blocker offen`)
  }

  // --- Stale-Parität: Feld-Edit ⇒ «Prüfung nicht aktuell» einheitlich ------
  const draft = await (
    await api.get(`/api/runs/${runId}/fields/INTRO.APP.ABSTRACT`)
  ).json()
  await api.patch(`/api/runs/${runId}/fields/INTRO.APP.ABSTRACT`, {
    headers: mut(),
    data: {
      base_version_id: draft.current_version.draft_version_id,
      text: "Kurzer sauberer Abstract für den Paritätstest.",
    },
  })
  const afterEdit = await (
    await api.get(`/api/runs/${runId}/review/status`)
  ).json()
  expect(afterEdit.stale).toBe(true)

  for (const path of ["/review", "/export"]) {
    await page.goto(path)
    await expect(
      page.getByTestId("canonical-stale").first(),
      `Screen ${path} zeigt den einheitlichen Stale-Wortlaut`
    ).toHaveText("Prüfung nicht aktuell", { timeout: 20_000 })
  }
})
