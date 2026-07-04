"use client"

import * as React from "react"
import { Button } from "@/components/ui/button"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"

interface EditorToolbarButtonProps {
  label: string
  icon: React.ReactNode
  onClick: () => void
  active?: boolean
  disabled?: boolean
}

/**
 * A compact toolbar control. Active formatting is shown with the "secondary"
 * variant + aria-pressed so keyboard/screen-reader users perceive the state.
 */
export function EditorToolbarButton({
  label,
  icon,
  onClick,
  active = false,
  disabled = false,
}: EditorToolbarButtonProps) {
  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <Button
            type="button"
            size="icon-sm"
            variant={active ? "secondary" : "ghost"}
            aria-label={label}
            aria-pressed={active}
            disabled={disabled}
            // Toolbar clicks must not steal focus from the editor selection.
            onMouseDown={(e) => e.preventDefault()}
            onClick={onClick}
          />
        }
      >
        {icon}
      </TooltipTrigger>
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  )
}
