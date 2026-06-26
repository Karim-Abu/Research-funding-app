import { describe, it, expect, vi, afterEach } from "vitest"
import {
  escapeHtml,
  textToHtml,
  copyPlain,
  copyFormatted,
  formattedCopySupported,
  ClipboardError,
} from "@/lib/clipboard"

function setClipboard(value: unknown) {
  Object.defineProperty(navigator, "clipboard", { value, configurable: true })
}

afterEach(() => {
  setClipboard(undefined)
  delete (globalThis as { ClipboardItem?: unknown }).ClipboardItem
})

describe("clipboard helpers", () => {
  it("escapeHtml neutralises script-relevant characters", () => {
    expect(escapeHtml(`<script>x('a')</script> & "q"`)).toBe(
      "&lt;script&gt;x(&#39;a&#39;)&lt;/script&gt; &amp; &quot;q&quot;"
    )
  })

  it("textToHtml builds only paragraphs/lists and escapes content", () => {
    const html = textToHtml("Absatz eins\n\n- Punkt A\n- <b>B</b>")
    expect(html).toContain("<p>Absatz eins</p>")
    expect(html).toContain("<ul><li>Punkt A</li><li>&lt;b&gt;B&lt;/b&gt;</li></ul>")
    expect(html).not.toContain("<b>")
    expect(html).not.toContain("<script")
  })

  it("copyPlain writes only the given text, Unicode preserved", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    setClipboard({ writeText })
    await copyPlain("Müller & Söhne über Förderfähigkeit üöä")
    expect(writeText).toHaveBeenCalledWith("Müller & Söhne über Förderfähigkeit üöä")
  })

  it("copyPlain throws ClipboardError when the API is unavailable", async () => {
    setClipboard(undefined)
    await expect(copyPlain("x")).rejects.toBeInstanceOf(ClipboardError)
  })

  it("copyFormatted writes text/html + text/plain via ClipboardItem", async () => {
    const write = vi.fn().mockResolvedValue(undefined)
    const writeText = vi.fn().mockResolvedValue(undefined)
    setClipboard({ write, writeText })
    const seen: Record<string, unknown>[] = []
    ;(globalThis as { ClipboardItem?: unknown }).ClipboardItem = class {
      constructor(data: Record<string, unknown>) {
        seen.push(data)
      }
    }
    expect(formattedCopySupported()).toBe(true)
    await copyFormatted("Text üä")
    expect(write).toHaveBeenCalledTimes(1)
    expect(Object.keys(seen[0])).toEqual(["text/html", "text/plain"])
  })

  it("copyFormatted falls back to plain text when ClipboardItem is unsupported", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    setClipboard({ writeText })
    await copyFormatted("nur Text")
    expect(writeText).toHaveBeenCalledWith("nur Text")
  })
})
