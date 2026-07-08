"use client"

// Tiptap rich-text editor for the Entwurf field. Encapsulated so the workspace
// shell stays simple. The canonical value to the outside is ALWAYS plain text
// (onChange(plainText)); formatting lives only in a per-session sessionStorage
// cache (see lib/rich-editor-cache.ts). Backend + Innolink stay plain text.

import * as React from "react"
import {
  EditorContent,
  Extension,
  useEditor,
  type Editor,
  type JSONContent,
} from "@tiptap/react"
import StarterKit from "@tiptap/starter-kit"
import Placeholder from "@tiptap/extension-placeholder"
import Highlight from "@tiptap/extension-highlight"
import { TextStyle } from "@tiptap/extension-text-style"
import { Color } from "@tiptap/extension-color"
import TextAlign from "@tiptap/extension-text-align"
import { Plugin } from "@tiptap/pm/state"
import { Decoration, DecorationSet } from "@tiptap/pm/view"
import { cn } from "@/lib/utils"
import { placeholderMatches } from "@/lib/draft-view"
import {
  buildTiptapContentFromPlainText,
  serializeTiptapToPortalPlainText,
  normalizePortalPlainText,
  isSafeLinkHref,
} from "@/lib/rich-editor-content"
import {
  hashServerText,
  isRichCacheAllowed,
  readRichEditorSessionCache,
  writeRichEditorSessionCache,
  clearRichEditorSessionCache,
  clearProjectRichEditorSessionCache,
} from "@/lib/rich-editor-cache"
import { EditorToolbar } from "@/components/editor/editor-toolbar"

export interface RichTextEditorHandle {
  focus: () => void
  getPlainText: () => string
  insertTextAtCursor: (text: string) => void
  /** Select the Nth placeholder in the document (best effort; may no-op). */
  selectPlaceholder: (index: number) => void
  clearFormatCache: () => void
}

interface RichTextEditorProps {
  /** Field id — identity; a change re-initialises the editor for the new field. */
  fieldKey: string
  /** Server plain text (source of truth for (re)initialisation). */
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

// PM plugin: highlight [[…]]/TODO/tbd tokens that live inside a SINGLE text node.
// Tokens split across nodes by formatting are intentionally skipped (no crash);
// the banner still detects them via the plain text.
const PlaceholderHighlight = Extension.create({
  name: "placeholderHighlight",
  addProseMirrorPlugins() {
    return [
      new Plugin({
        props: {
          decorations(state) {
            const decos: Decoration[] = []
            state.doc.descendants((node, pos) => {
              if (!node.isText || !node.text) return
              for (const m of placeholderMatches(node.text)) {
                decos.push(
                  Decoration.inline(pos + m.start, pos + m.end, {
                    style:
                      "background-color: rgba(234,179,8,0.18); border-radius: 2px;",
                  })
                )
              }
            })
            return DecorationSet.create(state.doc, decos)
          },
        },
      }),
    ]
  },
})

/** PM positions of placeholders found within single text nodes, in order. */
function findPlaceholderPositions(editor: Editor): { from: number; to: number }[] {
  const ranges: { from: number; to: number }[] = []
  editor.state.doc.descendants((node, pos) => {
    if (!node.isText || !node.text) return
    for (const m of placeholderMatches(node.text)) {
      ranges.push({ from: pos + m.start, to: pos + m.end })
    }
  })
  return ranges
}

export const RichTextEditor = React.forwardRef<RichTextEditorHandle, RichTextEditorProps>(
  function RichTextEditor(props, ref) {
    const {
      fieldKey,
      serverText,
      projectId,
      dataClass,
      fieldLabel,
      placeholder,
      spell,
      minHeightClass,
      onChange,
      onSave,
      saveDisabled,
    } = props

    // Stable refs so the editor callbacks never capture stale props.
    const onChangeRef = React.useRef(onChange)
    const onSaveRef = React.useRef(onSave)
    const saveDisabledRef = React.useRef(saveDisabled)
    React.useEffect(() => {
      onChangeRef.current = onChange
      onSaveRef.current = onSave
      saveDisabledRef.current = saveDisabled
    })

    const cacheAllowed = Boolean(projectId) && isRichCacheAllowed(dataClass)
    const serverTextHash = React.useMemo(() => hashServerText(serverText), [serverText])
    const debounceRef = React.useRef<ReturnType<typeof setTimeout> | null>(null)

    // R4.4: Alt-Cache-Bereinigung — wird ein nicht-öffentliches Projekt
    // geladen, werden vorhandene (vor dem Fix geschriebene) Einträge entfernt.
    React.useEffect(() => {
      if (projectId && !cacheAllowed) clearProjectRichEditorSessionCache(projectId)
    }, [projectId, cacheAllowed])

    // Content for the CURRENT field: cache hit → rich JSON, else built from the
    // server plain text. Used at creation and on every field switch (setContent).
    function resolveContent(): JSONContent {
      if (cacheAllowed && projectId) {
        const entry = readRichEditorSessionCache(projectId, fieldKey, serverTextHash)
        if (entry) return entry.tiptapJson
      }
      return buildTiptapContentFromPlainText(serverText)
    }

    function writeCache(editor: Editor) {
      if (!cacheAllowed || !projectId) return
      const json = editor.getJSON()
      writeRichEditorSessionCache({
        projectId,
        fieldId: fieldKey,
        serverTextHash: hashServerText(serializeTiptapToPortalPlainText(json)),
        plainTextSnapshot: serializeTiptapToPortalPlainText(json),
        tiptapJson: json,
      })
    }

    const editor = useEditor(
      {
        immediatelyRender: false,
        extensions: [
          StarterKit.configure({
            link: {
              openOnClick: false,
              autolink: false,
              protocols: ["http", "https", "mailto"],
              HTMLAttributes: { rel: "noopener noreferrer nofollow", target: "_blank" },
              validate: (href: string) => isSafeLinkHref(href),
            },
          }),
          TextStyle,
          Color,
          Highlight,
          TextAlign.configure({ types: ["heading", "paragraph"] }),
          Placeholder.configure({
            placeholder: placeholder ?? "Für dieses Feld liegt noch kein Entwurf vor.",
          }),
          PlaceholderHighlight,
        ],
        content: resolveContent(),
        editorProps: {
          attributes: {
            class: cn("rf-rich-editor focus:outline-none", minHeightClass),
            role: "textbox",
            "aria-multiline": "true",
            "aria-label": `Entwurf ${fieldLabel}`,
            spellcheck: spell === "off" ? "false" : "true",
            lang: spell === "en" ? "en" : "de-CH",
          },
          handleKeyDown(_view, event) {
            if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
              event.preventDefault()
              if (!saveDisabledRef.current) onSaveRef.current?.()
              return true
            }
            return false
          },
        },
        onUpdate({ editor }) {
          const plain = serializeTiptapToPortalPlainText(editor.getJSON())
          onChangeRef.current(plain) // immediate — counter/placeholder stay live
          if (debounceRef.current) clearTimeout(debounceRef.current)
          debounceRef.current = setTimeout(() => writeCache(editor), 500)
        },
      },
      // ONE editor instance for the component's life. Switching fields swaps the
      // content via setContent (below) — never destroys/recreates the editor, so
      // the toolbar's useEditorState never runs against a torn-down editor.
      []
    )

    // Reflect spellcheck/lang changes onto the live contenteditable.
    React.useEffect(() => {
      if (!editor) return
      const dom = editor.view.dom as HTMLElement
      dom.setAttribute("spellcheck", spell === "off" ? "false" : "true")
      dom.setAttribute("lang", spell === "en" ? "en" : "de-CH")
    }, [editor, spell])

    // Field switch + out-of-band server-text changes. One effect:
    //  - first mount / field switch → load that field's content (cache-or-plain)
    //    and, if it differs from the server text, sync the parent so the counter,
    //    placeholder banner, save button and KI diff match the editor;
    //  - same field, server text persisted (same plain text) → re-key the cache;
    //  - same field, server text replaced (A2 accept / conflict) → rebuild.
    const firstRunRef = React.useRef(true)
    const prevFieldRef = React.useRef(fieldKey)
    React.useEffect(() => {
      if (!editor) return
      const first = firstRunRef.current
      const fieldChanged = !first && prevFieldRef.current !== fieldKey
      firstRunRef.current = false
      prevFieldRef.current = fieldKey

      if (first || fieldChanged) {
        if (fieldChanged) {
          editor.commands.setContent(resolveContent(), { emitUpdate: false })
        }
        const restored = serializeTiptapToPortalPlainText(editor.getJSON())
        if (normalizePortalPlainText(restored) !== normalizePortalPlainText(serverText)) {
          onChangeRef.current(restored)
        }
        return
      }

      const currentPlain = serializeTiptapToPortalPlainText(editor.getJSON())
      if (hashServerText(currentPlain) === serverTextHash) {
        writeCache(editor) // save persisted → re-key cache, keep formatting
        return
      }
      // Text replaced (A2 accept / conflict reload) → rebuild from plain text.
      editor.commands.setContent(buildTiptapContentFromPlainText(serverText), {
        emitUpdate: false,
      })
      writeCache(editor)
    }, [editor, fieldKey, serverTextHash])

    React.useEffect(() => {
      return () => {
        if (debounceRef.current) clearTimeout(debounceRef.current)
      }
    }, [])

    React.useImperativeHandle(
      ref,
      (): RichTextEditorHandle => ({
        focus: () => editor?.chain().focus().run(),
        getPlainText: () =>
          editor ? serializeTiptapToPortalPlainText(editor.getJSON()) : serverText,
        insertTextAtCursor: (text: string) => {
          if (!editor) return
          // Ensure separation from surrounding text, then insert at the cursor.
          editor.chain().focus().insertContent(text).run()
        },
        selectPlaceholder: (index: number) => {
          if (!editor) return
          const positions = findPlaceholderPositions(editor)
          if (positions.length === 0) {
            editor.chain().focus().run() // fallback: no jump, just focus
            return
          }
          const target = positions[index % positions.length]
          editor
            .chain()
            .focus()
            .setTextSelection({ from: target.from, to: target.to })
            .scrollIntoView()
            .run()
        },
        clearFormatCache: () => {
          if (projectId) clearRichEditorSessionCache(projectId, fieldKey)
          if (editor) {
            const plain = serializeTiptapToPortalPlainText(editor.getJSON())
            editor.commands.setContent(buildTiptapContentFromPlainText(plain), {
              emitUpdate: false,
            })
          }
        },
      }),
      [editor, projectId, fieldKey, serverText]
    )

    return (
      <div className="flex flex-col overflow-hidden rounded-lg border border-slate-200 bg-white">
        {editor && <EditorToolbar editor={editor} />}
        <EditorContent
          editor={editor}
          className={cn(
            "cursor-text bg-white px-4 py-3 text-sm leading-7 text-slate-950",
            minHeightClass
          )}
        />
      </div>
    )
  }
)
