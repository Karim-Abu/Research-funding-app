import { describe, it, expect, vi, afterEach } from "vitest"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import { http, HttpResponse } from "msw"
import { PortalTransfer } from "@/components/portal-transfer/portal-transfer"
import type { PortalFieldDraftDto } from "@/lib/fields"
import type { ReviewPackageDto } from "@/lib/review"
import { server } from "./server"

// Slice 3 (Council E2-A): each copy in the Innolink view records a server-side
// CopyEvent. Copying is never blocked (fail-open); warnings require a reason.

function setClipboard(value: unknown) {
  Object.defineProperty(navigator, "clipboard", { value, configurable: true })
}
afterEach(() => setClipboard(undefined))

function field(
  fieldId: string,
  text: string,
  overrides: Partial<PortalFieldDraftDto> = {}
): PortalFieldDraftDto {
  const count = [...text].length
  return {
    draft_id: fieldId,
    field_id: fieldId,
    field_name: "Abstract",
    status: "needs_review",
    current_version: {
      draft_version_id: `${fieldId}-v1`,
      text,
      character_count: count,
      created_by: "user",
      created_at: new Date("2026-06-25T10:00:00Z").toISOString(),
      content_hash: "h",
    },
    character_count: count,
    character_limit: 300,
    open_issue_count: 0,
    evidence_links: [],
    open_issues: [],
    ...overrides,
  }
}

function reviewPkg(): ReviewPackageDto {
  return {
    run_id: "r1",
    requirements: [],
    fields: [],
    findings: [],
    approval_status: "approved",
    blocker_count: 0,
    warning_count: 0,
    open_issues: [],
    review_package_version: "rpv-1",
    current_approval_scope_hash: "h".repeat(64),
    recheck_required: false,
    stale_finding_count: 0,
  }
}

const COPY_URL = "/api/runs/r1/fields/:field/copy-events"

function copyEventResponse(fieldId: string) {
  return {
    copy_event_id: "ce-1",
    field_id: fieldId,
    draft_version_id: `${fieldId}-v1`,
    client_warnings: [],
    server_warnings: [],
    override_reason_code: null,
    created_at: new Date("2026-07-05T09:00:00Z").toISOString(),
  }
}

describe("PortalTransfer copy governance (Slice 3)", () => {
  it("records exactly one CopyEvent for a warning-free copy, then writes clipboard", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    setClipboard({ writeText })
    const bodies: Array<Record<string, unknown>> = []
    server.use(
      http.post(COPY_URL, async ({ request }) => {
        bodies.push((await request.json()) as Record<string, unknown>)
        return HttpResponse.json(copyEventResponse("INTRO.APP.ABSTRACT"), {
          status: 201,
        })
      })
    )
    render(
      <PortalTransfer
        fields={[field("INTRO.APP.ABSTRACT", "Sauberer Feldtext.")]}
        review={reviewPkg()}
        runId="r1"
        copyEventsEnabled
      />
    )
    fireEvent.click(screen.getByRole("button", { name: "Text kopieren" }))

    await waitFor(() => expect(bodies).toHaveLength(1))
    expect(bodies[0]).toMatchObject({
      draft_version_id: "INTRO.APP.ABSTRACT-v1",
      client_warnings: [],
    })
    await waitFor(() =>
      expect(writeText).toHaveBeenCalledWith("Sauberer Feldtext.")
    )
    await waitFor(() => expect(screen.getByText(/Kopiert am/)).toBeInTheDocument())
  })

  it("requires an override reason before copying a warning field", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    setClipboard({ writeText })
    const bodies: Array<Record<string, unknown>> = []
    server.use(
      http.post(COPY_URL, async ({ request }) => {
        bodies.push((await request.json()) as Record<string, unknown>)
        return HttpResponse.json(
          {
            ...copyEventResponse("INTRO.APP.ABSTRACT"),
            client_warnings: ["open"],
            server_warnings: ["open"],
            override_reason_code: "portal_finalization",
          },
          { status: 201 }
        )
      })
    )
    render(
      <PortalTransfer
        fields={[
          field("INTRO.APP.ABSTRACT", "Teiltext [[Angabe ergänzen: Rest]]", {
            open_issue_count: 1,
          }),
        ]}
        review={reviewPkg()}
        runId="r1"
        copyEventsEnabled
      />
    )
    fireEvent.click(screen.getByRole("button", { name: "Trotzdem kopieren…" }))
    // The confirm button is disabled until a reason is chosen; no call yet.
    const confirm = screen.getByRole("button", { name: "Trotzdem kopieren" })
    expect(confirm).toBeDisabled()
    fireEvent.click(confirm)
    expect(bodies).toHaveLength(0)

    fireEvent.click(
      screen.getByLabelText("Feld wird im Portal fertiggestellt", { exact: false })
    )
    expect(screen.getByRole("button", { name: "Trotzdem kopieren" })).toBeEnabled()
    fireEvent.click(screen.getByRole("button", { name: "Trotzdem kopieren" }))

    await waitFor(() => expect(bodies).toHaveLength(1))
    expect(bodies[0]).toMatchObject({
      client_warnings: ["open"],
      override_reason_code: "portal_finalization",
    })
    await waitFor(() => expect(writeText).toHaveBeenCalled())
  })

  it("fails open: copies anyway and warns when logging errors (5xx)", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    setClipboard({ writeText })
    server.use(
      http.post(COPY_URL, () => HttpResponse.json({ code: "error" }, { status: 500 }))
    )
    render(
      <PortalTransfer
        fields={[field("INTRO.APP.ABSTRACT", "Sauberer Feldtext.")]}
        review={reviewPkg()}
        runId="r1"
        copyEventsEnabled
      />
    )
    fireEvent.click(screen.getByRole("button", { name: "Text kopieren" }))

    await waitFor(() =>
      expect(writeText).toHaveBeenCalledWith("Sauberer Feldtext.")
    )
    await waitFor(() =>
      expect(
        screen.getByText("Übernahme konnte nicht protokolliert werden.")
      ).toBeInTheDocument()
    )
  })

  it("does not call the server when copy logging is disabled (today's behavior)", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    setClipboard({ writeText })
    const calls = vi.fn()
    server.use(
      http.post(COPY_URL, () => {
        calls()
        return HttpResponse.json(copyEventResponse("INTRO.APP.ABSTRACT"), {
          status: 201,
        })
      })
    )
    render(
      <PortalTransfer
        fields={[field("INTRO.APP.ABSTRACT", "Sauberer Feldtext.")]}
        review={reviewPkg()}
        runId="r1"
        copyEventsEnabled={false}
      />
    )
    fireEvent.click(screen.getByRole("button", { name: "Text kopieren" }))
    await waitFor(() => expect(writeText).toHaveBeenCalled())
    expect(calls).not.toHaveBeenCalled()
  })
})
