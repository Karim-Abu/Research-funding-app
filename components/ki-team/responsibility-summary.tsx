import {
  ListChecks,
  Sparkles,
  UserRoundCheck,
  type LucideIcon,
} from "lucide-react"

const items: Array<{
  title: string
  text: string
  icon: LucideIcon
}> = [
  {
    title: "KI unterstützt",
    text: "Analyse und Entwurf",
    icon: Sparkles,
  },
  {
    title: "Regeln prüfen",
    text: "Pflichtfelder und Grenzen",
    icon: ListChecks,
  },
  {
    title: "Menschen entscheiden",
    text: "Inhalte und Freigaben",
    icon: UserRoundCheck,
  },
]

export function ResponsibilitySummary() {
  return (
    <section
      aria-label="Verantwortungsübersicht"
      className="flex flex-col overflow-hidden rounded-lg border border-border bg-card sm:flex-row sm:divide-x sm:divide-border"
    >
      {items.map((item) => {
        const Icon = item.icon
        return (
          <div
            key={item.title}
            className="flex flex-1 items-start gap-2.5 border-t border-border px-4 py-3.5 first:border-t-0 sm:border-t-0"
          >
            <Icon
              aria-hidden="true"
              className="mt-0.5 size-4 shrink-0 text-muted-foreground"
            />
            <div className="min-w-0">
              <p className="text-sm font-medium text-foreground">{item.title}</p>
              <p className="mt-0.5 text-sm text-muted-foreground">{item.text}</p>
            </div>
          </div>
        )
      })}
    </section>
  )
}
