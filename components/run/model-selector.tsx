"use client"

import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
} from "@/components/ui/select"

interface ModelSelectorProps {
  value: "auto" | "claude" | "openai"
  onChange: (value: "auto" | "claude" | "openai") => void
}

const MODEL_LABELS: Record<ModelSelectorProps["value"], string> = {
  auto: "Automatisch (empfohlen)",
  claude: "Claude",
  openai: "OpenAI",
}

/** Advanced (lead_admin only) — uses the permitted term "KI-Modell". */
export function ModelSelector({ value, onChange }: ModelSelectorProps) {
  return (
    <div className="flex flex-col gap-1.5">
      <label className="text-sm font-medium text-foreground">KI-Modell</label>
      <Select value={value} onValueChange={(v) => onChange(v as ModelSelectorProps["value"])}>
        <SelectTrigger className="w-full">
          <span className="truncate">{MODEL_LABELS[value]}</span>
        </SelectTrigger>
        <SelectContent>
          <SelectGroup>
            <SelectItem value="auto">Automatisch (empfohlen)</SelectItem>
            <SelectItem value="claude">Claude</SelectItem>
            <SelectItem value="openai">OpenAI</SelectItem>
          </SelectGroup>
        </SelectContent>
      </Select>
      {value === "auto" && (
        <p className="text-xs text-muted-foreground">
          wählt nach Vertraulichkeitsstufe
        </p>
      )}
    </div>
  )
}
