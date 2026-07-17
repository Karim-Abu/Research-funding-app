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
  iconClassName: string
}> = [
  {
    title: "KI bereitet vor",
    text: "Analysiert Quellen, ordnet Evidenz und formuliert Vorschläge.",
    icon: Sparkles,
    iconClassName: "bg-primary/10 text-primary",
  },
  {
    title: "Regeln prüfen reproduzierbar",
    text: "Kontrollieren Pflichtfelder, Limits, Partner- und Budgetregeln.",
    icon: ListChecks,
    iconClassName: "bg-muted text-foreground/70",
  },
  {
    title: "Sie geben frei",
    text: "Bestätigen Belege, Budgetfragen, Texte und die manuelle Übernahme.",
    icon: UserRoundCheck,
    iconClassName: "bg-status-partial/10 text-status-partial",
  },
]

export function ResponsibilitySummary() {
  return (
    <section
      aria-label="Verantwortungsübersicht"
      className="grid overflow-hidden rounded-xl border border-border bg-card sm:grid-cols-3 sm:divide-x sm:divide-border"
    >
      {items.map((item, index) => {
        const Icon = item.icon
        return (
          <div
            key={item.title}
            className={`flex items-start gap-3 p-4 sm:p-5 ${
              index > 0 ? "border-t border-border sm:border-t-0" : ""
            }`}
          >
            <span
              className={`flex size-9 shrink-0 items-center justify-center rounded-lg ${item.iconClassName}`}
            >
              <Icon aria-hidden="true" className="size-4.5" />
            </span>
            <div>
              <h2 className="text-sm font-semibold text-foreground">
                {item.title}
              </h2>
              <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
                {item.text}
              </p>
            </div>
          </div>
        )
      })}
    </section>
  )
}
