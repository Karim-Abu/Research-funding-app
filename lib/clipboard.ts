// Clipboard helpers for the Innolink transfer view (Milestone 8.1).
// Plain text is the default. Formatted copy is optional/experimental — Innolink
// may strip or alter HTML formatting. All HTML is escaped; raw text is never
// inserted via innerHTML.

export class ClipboardError extends Error {
  constructor(message = "Die Zwischenablage ist nicht verfügbar.") {
    super(message)
    this.name = "ClipboardError"
  }
}

export function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;")
}

/** Build minimal, sanitized HTML — only <p> and <ul><li>. No headings invented
 * from arbitrary text, no scripts/styles/handlers. */
export function textToHtml(text: string): string {
  const blocks = text.split(/\n\s*\n/)
  return blocks
    .map((block) => {
      const lines = block.split("\n").map((l) => l.replace(/\s+$/, ""))
      const nonEmpty = lines.filter((l) => l.trim().length > 0)
      if (nonEmpty.length === 0) return ""
      const isList = nonEmpty.every((l) => /^[-*]\s+/.test(l.trim()))
      if (isList) {
        const items = nonEmpty
          .map((l) => `<li>${escapeHtml(l.trim().replace(/^[-*]\s+/, ""))}</li>`)
          .join("")
        return `<ul>${items}</ul>`
      }
      return `<p>${nonEmpty.map(escapeHtml).join("<br>")}</p>`
    })
    .filter(Boolean)
    .join("")
}

function hasAsyncClipboard(): boolean {
  return (
    typeof navigator !== "undefined" &&
    typeof navigator.clipboard?.writeText === "function"
  )
}

/** True when text/html + text/plain copy via ClipboardItem is available. */
export function formattedCopySupported(): boolean {
  return (
    typeof navigator !== "undefined" &&
    typeof navigator.clipboard?.write === "function" &&
    typeof ClipboardItem !== "undefined"
  )
}

/** Default copy: plain text only. Throws ClipboardError if unavailable. */
export async function copyPlain(text: string): Promise<void> {
  if (!hasAsyncClipboard()) throw new ClipboardError()
  await navigator.clipboard.writeText(text)
}

/** Optional/experimental: text/html (sanitized) with a text/plain fallback in
 * the same clipboard write. Falls back to plain text if ClipboardItem is
 * unsupported or the rich write fails. */
export async function copyFormatted(text: string): Promise<void> {
  if (formattedCopySupported()) {
    try {
      const item = new ClipboardItem({
        "text/html": new Blob([textToHtml(text)], { type: "text/html" }),
        "text/plain": new Blob([text], { type: "text/plain" }),
      })
      await navigator.clipboard.write([item])
      return
    } catch {
      /* fall through to plain text */
    }
  }
  await copyPlain(text)
}
