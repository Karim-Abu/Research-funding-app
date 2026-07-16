import { test, expect, type APIRequestContext } from "@playwright/test"

// M9D / M9D.2 A2 Solution & Innovation technical smoke (API context).
//
// Flow B (deterministic run): A2 is deliberately UNAVAILABLE — createRedraft
// returns a safe 503 ("nicht verfügbar"), the endpoint is scoped to the Solution
// & Innovation field, and the draft is never mutated.
//
// Flow A (M9D.2 cloud-processing gate): a public/synthetic project + an explicit
// one-run cloud confirmation enables a cloud_assisted run, so createRedraft returns
// 202, the user accepts the suggestion, and a new agent DraftVersion is created with
// recheck_required. Flow A requires the backend started with AGENT_FAKE_PROVIDER=true
// (no real provider key needed).
const EMAIL = process.env.E2E_EMAIL ?? "anna.keller@example.test"
const PASSWORD = process.env.E2E_PASSWORD ?? "changeme-dev-lead"
const ORIGIN = "http://localhost:3000"
const SOL = "SOL.INNOVATION_SOLUTION.EDITOR"
const VC = "VC.BUSINESS_TARGETS_MODEL.EDITOR"
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

async function waitForOperation(
  request: APIRequestContext,
  operationId: string
): Promise<string> {
  let status = ""
  for (let i = 0; i < 60; i++) {
    const op = await request.get(`/api/operations/${operationId}`)
    status = (await op.json()).status
    if (["succeeded", "failed", "cancelled"].includes(status)) break
    await new Promise((r) => setTimeout(r, 500))
  }
  return status
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
    // Composite-Felder verlangen einen gewählten Zielabschnitt (Editor-UX).
    { headers: mut(), data: { base_version_id: base, target_section: "4.1" } }
  )
  expect(redraft.status()).toBe(503)
  expect((await redraft.json()).code).toBe("ai_unavailable")

  // A2 is scoped to the allow-list — a non-enabled field (INTRO.APP.NAME) 404s.
  const other = await page.request.post(
    `/api/runs/${runId}/fields/INTRO.APP.NAME/redrafts`,
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

test("M9E Value Creation: cloud A2 suggestion → accept → agent draft + recheck (API context)", async ({
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
          title: "E2E A2 Value Creation",
          description: "Value Creation cloud A2 smoke.",
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
      text: "Synthetic public project content for the value-creation A2 flow.",
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
  expect(sourceVersionId).not.toBe("")

  const confirmationId = (
    await (
      await page.request.post(
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
    ).json()
  ).confirmation_id

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
  const runId = accepted.resource_id
  expect(await waitForOperation(page.request, accepted.operation_id)).toBe("succeeded")

  // The Value Creation draft exists (M6 template) and supports A2 (M9E).
  const draft = await (
    await page.request.get(`/api/runs/${runId}/fields/${VC}`)
  ).json()
  const base = draft.current_version.draft_version_id

  const redraft = await page.request.post(
    `/api/runs/${runId}/fields/${VC}/redrafts`,
    // Composite-Felder verlangen einen gewählten Zielabschnitt (Editor-UX).
    { headers: mut(), data: { base_version_id: base, target_section: "3.1" } }
  )
  expect(redraft.status()).toBe(202)
  const redraftOp = (await redraft.json()).operation_id
  expect(await waitForOperation(page.request, redraftOp)).toBe("succeeded")

  const suggestion = (
    await (await page.request.get(`/api/operations/${redraftOp}`)).json()
  ).result
  expect(suggestion.field_id).toBe(VC)
  expect(suggestion.character_limit).toBe(15000)
  expect(suggestion.suggested_text).toContain("3.1")

  // Annahme-Schlüssel ist die Operation der Suggestion selbst (view.operation_id)
  // — seit A2 im normalen Lauf läuft, kann der Redraft eine bestehende
  // Suggestion wiederverwenden, die an ihrer ursprünglichen Operation hängt.
  const acceptRes = await page.request.patch(
    `/api/runs/${runId}/fields/${VC}`,
    {
      headers: mut(),
      data: {
        base_version_id: base,
        text: suggestion.suggested_text,
        source_operation_id: suggestion.operation_id,
      },
    }
  )
  expect(acceptRes.status()).toBe(200)
  const acceptedDraft = await acceptRes.json()
  expect(acceptedDraft.current_version.created_by).toBe("agent")
  expect(acceptedDraft.current_version.draft_version_id).not.toBe(base)

  const runAfter = await (await page.request.get(`/api/runs/${runId}`)).json()
  expect(runAfter.recheck_required).toBe(true)

  // A2 is not exposed on an unsupported field (Abstract/Exec Summary are now
  // enabled; INTRO.APP.NAME remains outside the A2 allow-list).
  const unsupported = await page.request.post(
    `/api/runs/${runId}/fields/INTRO.APP.NAME/redrafts`,
    { headers: mut(), data: { base_version_id: base } }
  )
  expect(unsupported.status()).toBe(404)

  await page.getByText("Anna Keller").first().click()
  await page.getByText("Abmelden").click()
  await expect(page).toHaveURL(/\/login/, { timeout: 20_000 })
})

test("Flow A: cloud confirmation enables A2 → accept → agent draft + recheck (API context)", async ({
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
          title: "E2E A2 Cloud Project",
          description: "Cloud-processing gate smoke.",
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
      text: "Synthetic public project content for the cloud A2 flow.",
      data_classification: CLASSIFICATION,
    },
  })

  // Wait for the source to be processed, then collect its version id.
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
  expect(sourceVersionId).not.toBe("")

  // Explicit one-run cloud-processing confirmation (M9D.2 privacy gate).
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
  expect(confirmation.status()).toBe(201)
  const confirmationId = (await confirmation.json()).confirmation_id

  // A cloud_assisted run is now allowed because of the confirmation.
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
  const runId = accepted.resource_id
  expect(await waitForOperation(page.request, accepted.operation_id)).toBe("succeeded")

  const draft = await (
    await page.request.get(`/api/runs/${runId}/fields/${SOL}`)
  ).json()
  const base = draft.current_version.draft_version_id

  // createRedraft is now AVAILABLE (202) — not the deterministic 503.
  const redraft = await page.request.post(
    `/api/runs/${runId}/fields/${SOL}/redrafts`,
    // Composite-Felder verlangen einen gewählten Zielabschnitt (Editor-UX).
    { headers: mut(), data: { base_version_id: base, target_section: "4.1" } }
  )
  expect(redraft.status()).toBe(202)
  const redraftOp = (await redraft.json()).operation_id
  expect(await waitForOperation(page.request, redraftOp)).toBe("succeeded")

  const suggestion = (
    await (await page.request.get(`/api/operations/${redraftOp}`)).json()
  ).result
  expect(suggestion.suggested_text).toBeTruthy()

  // Explicit accept → a new DraftVersion created_by=agent + recheck_required.
  // Annahme-Schlüssel = Operation der Suggestion (kann bei Reuse aus dem
  // normalen Lauf stammen), wie im echten UI-Client.
  const acceptRes = await page.request.patch(
    `/api/runs/${runId}/fields/${SOL}`,
    {
      headers: mut(),
      data: {
        base_version_id: base,
        text: suggestion.suggested_text,
        source_operation_id: suggestion.operation_id,
      },
    }
  )
  expect(acceptRes.status()).toBe(200)
  const accepted2 = await acceptRes.json()
  expect(accepted2.current_version.created_by).toBe("agent")
  expect(accepted2.current_version.draft_version_id).not.toBe(base)

  const runAfter = await (await page.request.get(`/api/runs/${runId}`)).json()
  expect(runAfter.recheck_required).toBe(true)

  await page.getByText("Anna Keller").first().click()
  await page.getByText("Abmelden").click()
  await expect(page).toHaveURL(/\/login/, { timeout: 20_000 })
})
