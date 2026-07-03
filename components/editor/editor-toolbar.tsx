"use client"

import * as React from "react"
import { type Editor, useEditorState } from "@tiptap/react"
import {
  Undo2,
  Redo2,
  Bold,
  Italic,
  Underline as UnderlineIcon,
  Strikethrough,
  List,
  ListOrdered,
  AlignLeft,
  AlignCenter,
  AlignRight,
  AlignJustify,
  Highlighter,
  Baseline,
  Link2,
  Link2Off,
  RemoveFormatting,
  ChevronDown,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { cn } from "@/lib/utils"
import { normalizeLinkHref } from "@/lib/rich-editor-content"
import { EditorToolbarButton } from "@/components/editor/editor-toolbar-button"

// A small, calm palette. Values live in the doc as inline styles only (never
// persisted — plain text carries no colour).
const TEXT_COLORS: { label: string; value: string }[] = [
  { label: "Standard", value: "" },
  { label: "Grau", value: "#475569" },
  { label: "Blau", value: "#1d4ed8" },
  { label: "Grün", value: "#15803d" },
  { label: "Rot", value: "#b91c1c" },
]

const HEADING_LEVELS = [1, 2, 3] as const

// Fallback when the editor is (briefly) destroyed — keeps the selector total.
const DEFAULT_TOOLBAR_STATE = {
  canUndo: false,
  canRedo: false,
  bold: false,
  italic: false,
  underline: false,
  strike: false,
  bulletList: false,
  orderedList: false,
  alignLeft: false,
  alignCenter: false,
  alignRight: false,
  alignJustify: false,
  highlight: false,
  link: false,
  isParagraph: true,
  h1: false,
  h2: false,
  h3: false,
}

function headingLabel(state: {
  isParagraph: boolean
  h1: boolean
  h2: boolean
  h3: boolean
}): string {
  if (state.h1) return "Überschrift 1"
  if (state.h2) return "Überschrift 2"
  if (state.h3) return "Überschrift 3"
  return "Normaltext"
}

export function EditorToolbar({ editor }: { editor: Editor }) {
  const s = useEditorState({
    editor,
    selector: ({ editor: e }) => {
      // Guard against a torn-down editor (unmount / StrictMode races): the
      // selector must never call .can()/.isActive() on a destroyed instance.
      if (!e || e.isDestroyed) return DEFAULT_TOOLBAR_STATE
      return {
      canUndo: e.can().undo(),
      canRedo: e.can().redo(),
      bold: e.isActive("bold"),
      italic: e.isActive("italic"),
      underline: e.isActive("underline"),
      strike: e.isActive("strike"),
      bulletList: e.isActive("bulletList"),
      orderedList: e.isActive("orderedList"),
      alignLeft: e.isActive({ textAlign: "left" }),
      alignCenter: e.isActive({ textAlign: "center" }),
      alignRight: e.isActive({ textAlign: "right" }),
      alignJustify: e.isActive({ textAlign: "justify" }),
      highlight: e.isActive("highlight"),
      link: e.isActive("link"),
      isParagraph: e.isActive("paragraph"),
      h1: e.isActive("heading", { level: 1 }),
      h2: e.isActive("heading", { level: 2 }),
      h3: e.isActive("heading", { level: 3 }),
      }
    },
  })

  const [linkOpen, setLinkOpen] = React.useState(false)
  const [linkValue, setLinkValue] = React.useState("")
  const [linkError, setLinkError] = React.useState(false)

  function openLinkDialog() {
    const current = editor.getAttributes("link").href as string | undefined
    setLinkValue(current ?? "")
    setLinkError(false)
    setLinkOpen(true)
  }

  function applyLink() {
    const href = normalizeLinkHref(linkValue)
    if (!href) {
      setLinkError(true)
      return
    }
    editor.chain().focus().extendMarkRange("link").setLink({ href }).run()
    setLinkOpen(false)
  }

  function removeLink() {
    editor.chain().focus().extendMarkRange("link").unsetLink().run()
    setLinkOpen(false)
  }

  return (
    <div
      role="toolbar"
      aria-label="Textformatierung"
      className="flex flex-wrap items-center gap-0.5 border-b border-border bg-muted/30 px-2 py-1"
    >
      <EditorToolbarButton
        label="Rückgängig"
        icon={<Undo2 className="size-4" />}
        onClick={() => editor.chain().focus().undo().run()}
        disabled={!s.canUndo}
      />
      <EditorToolbarButton
        label="Wiederholen"
        icon={<Redo2 className="size-4" />}
        onClick={() => editor.chain().focus().redo().run()}
        disabled={!s.canRedo}
      />

      <ToolbarDivider />

      {/* Heading / paragraph */}
      <DropdownMenu>
        <DropdownMenuTrigger
          render={
            <Button
              type="button"
              size="sm"
              variant="ghost"
              className="gap-1 px-2"
              onMouseDown={(e) => e.preventDefault()}
              aria-label="Absatzformat"
            />
          }
        >
          <span className="text-xs font-medium">{headingLabel(s)}</span>
          <ChevronDown className="size-3.5" />
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start">
          <DropdownMenuItem
            onClick={() => editor.chain().focus().setParagraph().run()}
            className={cn(s.isParagraph && "bg-accent")}
          >
            Normaltext
          </DropdownMenuItem>
          {HEADING_LEVELS.map((level) => (
            <DropdownMenuItem
              key={level}
              onClick={() => editor.chain().focus().toggleHeading({ level }).run()}
              className={cn(
                (level === 1 ? s.h1 : level === 2 ? s.h2 : s.h3) && "bg-accent"
              )}
            >
              Überschrift {level}
            </DropdownMenuItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>

      <ToolbarDivider />

      <EditorToolbarButton
        label="Fett"
        icon={<Bold className="size-4" />}
        active={s.bold}
        onClick={() => editor.chain().focus().toggleBold().run()}
      />
      <EditorToolbarButton
        label="Kursiv"
        icon={<Italic className="size-4" />}
        active={s.italic}
        onClick={() => editor.chain().focus().toggleItalic().run()}
      />
      <EditorToolbarButton
        label="Unterstrichen"
        icon={<UnderlineIcon className="size-4" />}
        active={s.underline}
        onClick={() => editor.chain().focus().toggleUnderline().run()}
      />
      <EditorToolbarButton
        label="Durchgestrichen"
        icon={<Strikethrough className="size-4" />}
        active={s.strike}
        onClick={() => editor.chain().focus().toggleStrike().run()}
      />

      <ToolbarDivider />

      <EditorToolbarButton
        label="Aufzählung"
        icon={<List className="size-4" />}
        active={s.bulletList}
        onClick={() => editor.chain().focus().toggleBulletList().run()}
      />
      <EditorToolbarButton
        label="Nummerierte Liste"
        icon={<ListOrdered className="size-4" />}
        active={s.orderedList}
        onClick={() => editor.chain().focus().toggleOrderedList().run()}
      />

      <ToolbarDivider />

      <EditorToolbarButton
        label="Linksbündig"
        icon={<AlignLeft className="size-4" />}
        active={s.alignLeft}
        onClick={() => editor.chain().focus().setTextAlign("left").run()}
      />
      <EditorToolbarButton
        label="Zentriert"
        icon={<AlignCenter className="size-4" />}
        active={s.alignCenter}
        onClick={() => editor.chain().focus().setTextAlign("center").run()}
      />
      <EditorToolbarButton
        label="Rechtsbündig"
        icon={<AlignRight className="size-4" />}
        active={s.alignRight}
        onClick={() => editor.chain().focus().setTextAlign("right").run()}
      />
      <EditorToolbarButton
        label="Blocksatz"
        icon={<AlignJustify className="size-4" />}
        active={s.alignJustify}
        onClick={() => editor.chain().focus().setTextAlign("justify").run()}
      />

      <ToolbarDivider />

      <EditorToolbarButton
        label="Hervorheben"
        icon={<Highlighter className="size-4" />}
        active={s.highlight}
        onClick={() => editor.chain().focus().toggleHighlight().run()}
      />

      {/* Text colour */}
      <DropdownMenu>
        <DropdownMenuTrigger
          render={
            <Button
              type="button"
              size="icon-sm"
              variant="ghost"
              onMouseDown={(e) => e.preventDefault()}
              aria-label="Textfarbe"
            />
          }
        >
          <Baseline className="size-4" />
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" className="min-w-40">
          {TEXT_COLORS.map((c) => (
            <DropdownMenuItem
              key={c.label}
              onClick={() =>
                c.value
                  ? editor.chain().focus().setColor(c.value).run()
                  : editor.chain().focus().unsetColor().run()
              }
            >
              <span
                className="size-3.5 rounded-full border border-border"
                style={{ backgroundColor: c.value || "transparent" }}
                aria-hidden
              />
              {c.label}
            </DropdownMenuItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>

      {/* Link */}
      <Popover open={linkOpen} onOpenChange={setLinkOpen}>
        <PopoverTrigger
          render={
            <Button
              type="button"
              size="icon-sm"
              variant={s.link ? "secondary" : "ghost"}
              aria-label="Link einfügen oder bearbeiten"
              aria-pressed={s.link}
              onMouseDown={(e) => e.preventDefault()}
              onClick={openLinkDialog}
            />
          }
        >
          <Link2 className="size-4" />
        </PopoverTrigger>
        <PopoverContent align="start" className="w-72">
          <label className="text-xs font-medium text-foreground" htmlFor="rt-link-input">
            Link-Adresse
          </label>
          <Input
            id="rt-link-input"
            value={linkValue}
            onChange={(e) => {
              setLinkValue(e.target.value)
              setLinkError(false)
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault()
                applyLink()
              }
            }}
            placeholder="https://…"
            aria-invalid={linkError}
          />
          {linkError && (
            <p role="alert" className="text-xs text-destructive">
              Nur http(s)- oder mailto-Adressen sind erlaubt.
            </p>
          )}
          <div className="flex items-center justify-between gap-2">
            <Button
              type="button"
              size="xs"
              variant="ghost"
              onClick={removeLink}
              disabled={!s.link}
            >
              <Link2Off className="mr-1 size-3.5" />
              Entfernen
            </Button>
            <Button type="button" size="xs" onClick={applyLink}>
              Übernehmen
            </Button>
          </div>
        </PopoverContent>
      </Popover>

      <ToolbarDivider />

      <EditorToolbarButton
        label="Formatierung entfernen"
        icon={<RemoveFormatting className="size-4" />}
        onClick={() => editor.chain().focus().unsetAllMarks().clearNodes().run()}
      />
    </div>
  )
}

function ToolbarDivider() {
  return <span className="mx-1 h-5 w-px shrink-0 bg-border" aria-hidden />
}
