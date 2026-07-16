// Test stub for the Tiptap RichTextEditor. ProseMirror needs real DOM ranges
// that jsdom doesn't provide, so unit tests replace the editor with a native
// <textarea> that mirrors the same aria-label, onChange (plain text) and handle.
// The real editor is exercised by Playwright e2e. Activate per test file:
//   vi.mock("@/components/editor/rich-text-editor",
//     async () => await import("./mocks/rich-text-editor"))

import * as React from "react"
import { placeholderMatches } from "@/lib/draft-view"

export interface RichTextEditorHandle {
  focus: () => void
  getPlainText: () => string
  insertTextAtCursor: (text: string) => void
  selectPlaceholder: (index: number) => void
  selectMatch: (query: string) => void
  getSelectedText: () => string
  deleteSelection: () => void
  clearFormatCache: () => void
}

interface StubProps {
  fieldKey: string
  serverText: string
  projectId?: string
  dataClass?: string | null
  fieldLabel: string
  placeholder?: string
  spell: "de" | "en" | "off"
  minHeightClass?: string
  onChange: (plainText: string) => void
  onSave?: () => void
  saveDisabled?: boolean
}

export const RichTextEditor = React.forwardRef<RichTextEditorHandle, StubProps>(
  function RichTextEditorStub(props, ref) {
    const {
      fieldKey,
      serverText,
      fieldLabel,
      placeholder,
      spell,
      minHeightClass,
      onChange,
      onSave,
      saveDisabled,
    } = props
    const [value, setValue] = React.useState(serverText)
    const taRef = React.useRef<HTMLTextAreaElement>(null)

    // Re-seed when the field changes (mirrors the real editor's recreation).
    const seededField = React.useRef(fieldKey)
    if (seededField.current !== fieldKey) {
      seededField.current = fieldKey
      if (value !== serverText) setValue(serverText)
    }

    React.useImperativeHandle(
      ref,
      () => ({
        focus: () => taRef.current?.focus(),
        getPlainText: () => value,
        insertTextAtCursor: (text: string) => {
          const node = taRef.current
          const pos = node ? node.selectionStart : value.length
          const next = value.slice(0, pos) + text + value.slice(pos)
          setValue(next)
          onChange(next)
        },
        selectPlaceholder: (index: number) => {
          const node = taRef.current
          if (!node) return
          const matches = placeholderMatches(value)
          if (matches.length === 0) {
            node.focus()
            return
          }
          const m = matches[index % matches.length]
          node.focus()
          node.setSelectionRange(m.start, m.end)
        },
        selectMatch: (query: string) => {
          const node = taRef.current
          if (!node) return
          node.focus()
          const idx = value.indexOf(query)
          if (idx >= 0) node.setSelectionRange(idx, idx + query.length)
        },
        getSelectedText: () => {
          const node = taRef.current
          if (!node) return ""
          return value.slice(node.selectionStart ?? 0, node.selectionEnd ?? 0)
        },
        deleteSelection: () => {
          const node = taRef.current
          if (!node || node.selectionStart === node.selectionEnd) return
          const next =
            value.slice(0, node.selectionStart) + value.slice(node.selectionEnd)
          setValue(next)
          onChange(next)
        },
        clearFormatCache: () => {},
      }),
      [value, onChange]
    )

    return (
      <textarea
        ref={taRef}
        aria-label={`Entwurf ${fieldLabel}`}
        value={value}
        placeholder={placeholder}
        spellCheck={spell !== "off"}
        lang={spell === "en" ? "en" : "de-CH"}
        className={minHeightClass}
        onChange={(e) => {
          setValue(e.target.value)
          onChange(e.target.value)
        }}
        onKeyDown={(e) => {
          if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
            e.preventDefault()
            if (!saveDisabled) onSave?.()
          }
        }}
      />
    )
  }
)
