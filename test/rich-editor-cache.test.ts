import { describe, it, expect, beforeEach } from "vitest"
import type { JSONContent } from "@tiptap/react"
import {
  getRichEditorCacheKey,
  hashServerText,
  isRichCacheAllowed,
  readRichEditorSessionCache,
  writeRichEditorSessionCache,
  clearRichEditorSessionCache,
  clearAllRichEditorSessionCache,
  clearProjectRichEditorSessionCache,
} from "@/lib/rich-editor-cache"

const json: JSONContent = {
  type: "doc",
  content: [{ type: "paragraph", content: [{ type: "text", text: "Hallo" }] }],
}

beforeEach(() => {
  sessionStorage.clear()
})

describe("hashServerText", () => {
  it("is stable and ignores trivial whitespace differences", () => {
    expect(hashServerText("Hallo Welt")).toBe(hashServerText("Hallo Welt"))
    expect(hashServerText("Hallo Welt  \r\n")).toBe(hashServerText("Hallo Welt"))
    expect(hashServerText("Hallo Welt")).not.toBe(hashServerText("Hallo Mars"))
  })
})

describe("isRichCacheAllowed (R4.4 — nur D0/public, fail-closed)", () => {
  it("erlaubt ausschliesslich explizit öffentliche Projekte", () => {
    expect(isRichCacheAllowed("public")).toBe(true)
    expect(isRichCacheAllowed("D0")).toBe(true)
    expect(isRichCacheAllowed(" Public ")).toBe(true)
  })

  it("sperrt internal/confidential/nda/restricted und alles Unbekannte", () => {
    expect(isRichCacheAllowed("internal")).toBe(false)
    expect(isRichCacheAllowed("confidential")).toBe(false)
    expect(isRichCacheAllowed("nda")).toBe(false)
    expect(isRichCacheAllowed("d3")).toBe(false)
    expect(isRichCacheAllowed("restricted")).toBe(false)
    expect(isRichCacheAllowed("gesperrt")).toBe(false)
    // fail-closed: fehlende/unklare Einstufung ⇒ kein Cache
    expect(isRichCacheAllowed(undefined)).toBe(false)
    expect(isRichCacheAllowed(null)).toBe(false)
    expect(isRichCacheAllowed("")).toBe(false)
    expect(isRichCacheAllowed("top-secret")).toBe(false)
  })
})

describe("clearProjectRichEditorSessionCache (R4.4 — Alt-Cache-Bereinigung)", () => {
  it("entfernt nur die Einträge des betroffenen Projekts", () => {
    const hash = hashServerText("x")
    for (const projectId of ["p1", "p2"]) {
      writeRichEditorSessionCache({
        projectId, fieldId: "F.A", serverTextHash: hash,
        plainTextSnapshot: "x", tiptapJson: json,
      })
    }
    clearProjectRichEditorSessionCache("p1")
    expect(readRichEditorSessionCache("p1", "F.A", hash)).toBeNull()
    expect(readRichEditorSessionCache("p2", "F.A", hash)).not.toBeNull()
  })
})

describe("session cache read/write/clear", () => {
  it("returns the entry only on matching project/field/hash", () => {
    const hash = hashServerText("server text")
    writeRichEditorSessionCache({
      projectId: "p1",
      fieldId: "F.A",
      serverTextHash: hash,
      plainTextSnapshot: "Hallo",
      tiptapJson: json,
    })
    expect(readRichEditorSessionCache("p1", "F.A", hash)?.tiptapJson).toEqual(json)
    // wrong hash → discarded
    expect(readRichEditorSessionCache("p1", "F.A", "other")).toBeNull()
    // and the stale entry was removed
    expect(sessionStorage.getItem(getRichEditorCacheKey("p1", "F.A"))).toBeNull()
  })

  it("clears a single field and all fields", () => {
    const hash = hashServerText("x")
    writeRichEditorSessionCache({ projectId: "p1", fieldId: "F.A", serverTextHash: hash, plainTextSnapshot: "x", tiptapJson: json })
    writeRichEditorSessionCache({ projectId: "p1", fieldId: "F.B", serverTextHash: hash, plainTextSnapshot: "x", tiptapJson: json })

    clearRichEditorSessionCache("p1", "F.A")
    expect(readRichEditorSessionCache("p1", "F.A", hash)).toBeNull()
    expect(readRichEditorSessionCache("p1", "F.B", hash)).not.toBeNull()

    clearAllRichEditorSessionCache()
    expect(readRichEditorSessionCache("p1", "F.B", hash)).toBeNull()
  })
})
