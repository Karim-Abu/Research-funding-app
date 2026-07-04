// Pure serialization between the Innosuisse portal plain text (the only value
// the backend stores) and a Tiptap document. No React, no DOM — unit-testable.
//
// Rules (agreed with the product owner):
//  - Plain text stays the single source of truth: character limit, placeholder
//    detection, copy-to-portal, export and the KI diff all run on it.
//  - Paragraphs and headings are separated by a blank line; a heading is a plain
//    line WITHOUT any markdown prefix.
//  - Bullet-list items become "- …", ordered-list items become "1. …".
//  - Bold / italic / underline / color / highlight produce NO extra characters.
//  - "[[Angabe ergänzen: …]]" placeholders survive verbatim as ordinary text.

import type { JSONContent } from "@tiptap/react"

// ---------------------------------------------------------------------------
// Link safety — used by both the Tiptap Link `validate` and the toolbar dialog.
// Only http(s)/mailto are allowed; javascript:/data: and friends are rejected.
// ---------------------------------------------------------------------------
const SAFE_LINK_RE = /^(https?:\/\/|mailto:)/i

export function isSafeLinkHref(href: string): boolean {
  return SAFE_LINK_RE.test(href.trim())
}

/** Trim + accept a safe href, or add "https://" to a bare domain, else null. */
export function normalizeLinkHref(raw: string): string | null {
  const value = raw.trim()
  if (value.length === 0) return null
  if (isSafeLinkHref(value)) return value
  // Bare domain like "example.com/x" → assume https; reject anything with a
  // scheme we didn't allow (e.g. "javascript:…", "data:…").
  if (/^[^\s:]+\.[^\s:]/.test(value) && !value.includes(":")) {
    return `https://${value}`
  }
  return null
}

// ---------------------------------------------------------------------------
// Normalisation — used for the cache hash so trivial newline/whitespace
// differences do not needlessly invalidate the session cache.
// ---------------------------------------------------------------------------
export function normalizePortalPlainText(text: string): string {
  return text
    .replace(/\r\n?/g, "\n") // CRLF/CR → LF
    .replace(/[ \t]+$/gm, "") // trailing spaces per line
    .replace(/\n{3,}/g, "\n\n") // collapse 3+ blank lines
    .replace(/\s+$/, "") // trailing whitespace at end
}

// ---------------------------------------------------------------------------
// Tiptap JSON → portal plain text.
// ---------------------------------------------------------------------------
function nodeText(node: JSONContent): string {
  if (node.type === "text") return node.text ?? ""
  if (!node.content) return ""
  // hard_break inside a paragraph → newline; otherwise concatenate inline text.
  return node.content
    .map((child) => (child.type === "hardBreak" ? "\n" : nodeText(child)))
    .join("")
}

function listToText(list: JSONContent, ordered: boolean): string {
  const items = list.content ?? []
  return items
    .map((item, index) => {
      const marker = ordered ? `${index + 1}. ` : "- "
      // A list item wraps block nodes (usually a single paragraph).
      const inner = (item.content ?? [])
        .map((block) => nodeText(block))
        .filter((line) => line.length > 0)
        .join("\n")
      return `${marker}${inner}`
    })
    .join("\n")
}

function blockToText(node: JSONContent): string {
  switch (node.type) {
    case "bulletList":
      return listToText(node, false)
    case "orderedList":
      return listToText(node, true)
    case "horizontalRule":
      return ""
    case "blockquote":
      return (node.content ?? []).map(blockToText).join("\n\n")
    default:
      // paragraph, heading, codeBlock, … → their inline text as one line block.
      return nodeText(node)
  }
}

/** Serialize a Tiptap document (JSONContent) to portal plain text. */
export function serializeTiptapToPortalPlainText(doc: JSONContent): string {
  const blocks = doc.content ?? []
  const out = blocks.map(blockToText)
  return normalizePortalPlainText(out.join("\n\n"))
}

// ---------------------------------------------------------------------------
// Portal plain text → Tiptap JSON (used when no rich cache exists yet).
// Blank-line separated blocks become paragraphs; "- "/"1. " runs become lists.
// ---------------------------------------------------------------------------
const BULLET_RE = /^[-•]\s+(.*)$/
const ORDERED_RE = /^\d+[.)]\s+(.*)$/

function paragraph(text: string): JSONContent {
  return text.length === 0
    ? { type: "paragraph" }
    : { type: "paragraph", content: [{ type: "text", text }] }
}

function listItem(text: string): JSONContent {
  return { type: "listItem", content: [paragraph(text)] }
}

export function buildTiptapContentFromPlainText(text: string): JSONContent {
  const normalized = normalizePortalPlainText(text)
  if (normalized.length === 0) {
    return { type: "doc", content: [{ type: "paragraph" }] }
  }
  const blocks = normalized.split(/\n{2,}/)
  const content: JSONContent[] = []

  for (const block of blocks) {
    const lines = block.split("\n")
    const allBullet = lines.every((l) => BULLET_RE.test(l))
    const allOrdered = lines.every((l) => ORDERED_RE.test(l))

    if (lines.length > 0 && allBullet) {
      content.push({
        type: "bulletList",
        content: lines.map((l) => listItem(BULLET_RE.exec(l)![1])),
      })
    } else if (lines.length > 0 && allOrdered) {
      content.push({
        type: "orderedList",
        content: lines.map((l) => listItem(ORDERED_RE.exec(l)![1])),
      })
    } else {
      // Mixed/plain block → a paragraph; internal single newlines become
      // hard breaks so line structure is preserved.
      const inline: JSONContent[] = []
      lines.forEach((line, i) => {
        if (i > 0) inline.push({ type: "hardBreak" })
        if (line.length > 0) inline.push({ type: "text", text: line })
      })
      content.push(inline.length > 0 ? { type: "paragraph", content: inline } : { type: "paragraph" })
    }
  }

  return { type: "doc", content: content.length > 0 ? content : [{ type: "paragraph" }] }
}
