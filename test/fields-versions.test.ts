// RUN 4B — Versions-Client: Metadaten-Liste + Einzelversion + Fehler-Mapping.
import { describe, it, expect } from "vitest"
import { http, HttpResponse } from "msw"
import { server } from "./server"

import {
  FieldError,
  getFieldVersion,
  listFieldVersions,
} from "@/lib/fields"

const RUN = "r1"
const FIELD = "INTRO.APP.ABSTRACT"

function summary(overrides: Record<string, unknown> = {}) {
  return {
    draft_version_id: "v2",
    created_at: "2026-07-23T10:00:00Z",
    created_by: "user",
    generation_kind: null,
    character_count: 42,
    is_current: true,
    ...overrides,
  }
}

describe("listFieldVersions", () => {
  it("liefert die Metadaten-Liste (neueste zuerst) ohne Volltexte", async () => {
    server.use(
      http.get(`/api/runs/${RUN}/fields/${FIELD}/versions`, () =>
        HttpResponse.json({
          versions: [
            summary(),
            summary({
              draft_version_id: "v1",
              created_by: "template",
              generation_kind: "rule_template",
              is_current: false,
            }),
          ],
        })
      )
    )
    const versions = await listFieldVersions(RUN, FIELD)
    expect(versions).toHaveLength(2)
    expect(versions[0].is_current).toBe(true)
    expect(versions[1].created_by).toBe("template")
    expect(versions[1].generation_kind).toBe("rule_template")
    expect("text" in versions[0]).toBe(false)
  })

  it("leere/fehlende Liste wird zu []", async () => {
    server.use(
      http.get(`/api/runs/${RUN}/fields/${FIELD}/versions`, () =>
        HttpResponse.json({})
      )
    )
    expect(await listFieldVersions(RUN, FIELD)).toEqual([])
  })

  it("404 → deutsches Fehler-Mapping", async () => {
    server.use(
      http.get(`/api/runs/${RUN}/fields/${FIELD}/versions`, () =>
        HttpResponse.json({ code: "not_found" }, { status: 404 })
      )
    )
    await expect(listFieldVersions(RUN, FIELD)).rejects.toMatchObject({
      name: "FieldError",
      status: 404,
      code: "not_found",
    })
  })
})

describe("getFieldVersion", () => {
  it("liefert den Volltext einer unveränderlichen Altversion", async () => {
    server.use(
      http.get(`/api/runs/${RUN}/fields/${FIELD}/versions/v1`, () =>
        HttpResponse.json({
          draft_version_id: "v1",
          text: "Alter Abstract-Text.",
          character_count: 20,
          created_by: "template",
          created_at: "2026-07-20T08:00:00Z",
          content_hash: "abc",
          generation_kind: "rule_template",
        })
      )
    )
    const version = await getFieldVersion(RUN, FIELD, "v1")
    expect(version.text).toBe("Alter Abstract-Text.")
    expect(version.created_by).toBe("template")
  })

  it("Fehler bleibt ein FieldError (409-Beispiel)", async () => {
    server.use(
      http.get(`/api/runs/${RUN}/fields/${FIELD}/versions/v1`, () =>
        HttpResponse.json({ code: "conflict" }, { status: 409 })
      )
    )
    await expect(getFieldVersion(RUN, FIELD, "v1")).rejects.toBeInstanceOf(
      FieldError
    )
  })
})
