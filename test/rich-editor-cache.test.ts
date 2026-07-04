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

describe("isRichCacheAllowed", () => {
  it("allows D0–D2 and unknown, disables restricted/NDA classes", () => {
    expect(isRichCacheAllowed("public")).toBe(true)
    expect(isRichCacheAllowed("internal")).toBe(true)
    expect(isRichCacheAllowed("confidential")).toBe(true)
    expect(isRichCacheAllowed(undefined)).toBe(true)
    expect(isRichCacheAllowed("d3")).toBe(false)
    expect(isRichCacheAllowed("nda")).toBe(false)
    expect(isRichCacheAllowed("restricted")).toBe(false)
    expect(isRichCacheAllowed("gesperrt")).toBe(false)
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
