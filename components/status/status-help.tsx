"use client"

// Accessible inline help for status tiles and badges. Uses a Popover with a
// real button trigger so the explanation works with keyboard, touch and
// screen readers — hover (openOnHover) is an addition, never the only path.

import { Info } from "lucide-react"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import { cn } from "@/lib/utils"

export function StatusHelp({
  label,
  text,
  className,
}: {
  /** Name of the status the help explains (used for the aria-label). */
  label: string
  /** Short, non-technical explanation. */
  text: string
  className?: string
}) {
  return (
    <Popover>
      <PopoverTrigger
        openOnHover
        delay={200}
        aria-label={`Erklärung zu „${label}“`}
        className={cn(
          "inline-flex size-4 shrink-0 items-center justify-center rounded-full text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring",
          className
        )}
      >
        <Info className="size-3.5" aria-hidden />
      </PopoverTrigger>
      <PopoverContent side="bottom" className="max-w-64 text-xs">
        {text}
      </PopoverContent>
    </Popover>
  )
}
