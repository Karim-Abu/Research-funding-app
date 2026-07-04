import { describe, it, expect } from "vitest"
import type { JSONContent } from "@tiptap/react"
import {
  normalizePortalPlainText,
  serializeTiptapToPortalPlainText,
  buildTiptapContentFromPlainText,
  isSafeLinkHref,
  normalizeLinkHref,
} from "@/lib/rich-editor-content"

describe("normalizePortalPlainText", () => {
  it("normalises newlines and trailing whitespace", () => {
    expect(normalizePortalPlainText("a  \r\nb\r\n\r\n\r\nc  ")).toBe("a\nb\n\nc")
  })
})

describe("serializeTiptapToPortalPlainText", () => {
  it("serialises headings as plain lines and paragraphs blank-line separated", () => {
    const doc: JSONContent = {
      type: "doc",
      content: [
        { type: "heading", attrs: { level: 1 }, content: [{ type: "text", text: "Titel" }] },
        { type: "paragraph", content: [{ type: "text", text: "Erster Absatz." }] },
      ],
    }
    expect(serializeTiptapToPortalPlainText(doc)).toBe("Titel\n\nErster Absatz.")
  })

  it("serialises bullet and ordered lists with plain markers", () => {
    const doc: JSONContent = {
      type: "doc",
      content: [
        {
          type: "bulletList",
          content: [
            { type: "listItem", content: [{ type: "paragraph", content: [{ type: "text", text: "Alpha" }] }] },
            { type: "listItem", content: [{ type: "paragraph", content: [{ type: "text", text: "Beta" }] }] },
          ],
        },
        {
          type: "orderedList",
          content: [
            { type: "listItem", content: [{ type: "paragraph", content: [{ type: "text", text: "Eins" }] }] },
            { type: "listItem", content: [{ type: "paragraph", content: [{ type: "text", text: "Zwei" }] }] },
          ],
        },
      ],
    }
    expect(serializeTiptapToPortalPlainText(doc)).toBe("- Alpha\n- Beta\n\n1. Eins\n2. Zwei")
  })

  it("emits no special characters for bold/highlight/colour marks", () => {
    const doc: JSONContent = {
      type: "doc",
      content: [
        {
          type: "paragraph",
          content: [
            { type: "text", text: "Ein ", marks: [] },
            { type: "text", text: "fetter", marks: [{ type: "bold" }] },
            { type: "text", text: " und ", marks: [] },
            { type: "text", text: "markierter", marks: [{ type: "highlight" }] },
            { type: "text", text: " Teil." },
          ],
        },
      ],
    }
    expect(serializeTiptapToPortalPlainText(doc)).toBe("Ein fetter und markierter Teil.")
  })

  it("keeps [[Angabe ergänzen: …]] placeholders verbatim", () => {
    const doc: JSONContent = {
      type: "doc",
      content: [
        { type: "paragraph", content: [{ type: "text", text: "[[Angabe ergänzen: Ziel]]" }] },
      ],
    }
    expect(serializeTiptapToPortalPlainText(doc)).toBe("[[Angabe ergänzen: Ziel]]")
  })
})

describe("buildTiptapContentFromPlainText → serialize round-trip", () => {
  it("round-trips paragraphs, lists and placeholders", () => {
    const text = "Titelzeile\n\n- Alpha\n- Beta\n\n1. Eins\n2. Zwei\n\n[[Angabe ergänzen: X]]"
    const doc = buildTiptapContentFromPlainText(text)
    expect(serializeTiptapToPortalPlainText(doc)).toBe(text)
  })

  it("produces an empty paragraph for empty text", () => {
    expect(buildTiptapContentFromPlainText("")).toEqual({
      type: "doc",
      content: [{ type: "paragraph" }],
    })
  })
})

describe("link safety", () => {
  it("accepts http(s) and mailto, rejects dangerous schemes", () => {
    expect(isSafeLinkHref("https://example.com")).toBe(true)
    expect(isSafeLinkHref("http://example.com")).toBe(true)
    expect(isSafeLinkHref("mailto:a@b.ch")).toBe(true)
    expect(isSafeLinkHref("javascript:alert(1)")).toBe(false)
    expect(isSafeLinkHref("data:text/html,x")).toBe(false)
  })

  it("normalises bare domains to https and rejects bad schemes", () => {
    expect(normalizeLinkHref("  example.com/x ")).toBe("https://example.com/x")
    expect(normalizeLinkHref("https://ok.ch")).toBe("https://ok.ch")
    expect(normalizeLinkHref("javascript:alert(1)")).toBeNull()
    expect(normalizeLinkHref("")).toBeNull()
  })
})
