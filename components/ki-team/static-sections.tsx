import {
  Ban,
  ShieldCheck,
  UserRoundCheck,
  XCircle,
} from "lucide-react"
import { getKiTeamPhases, kiTeamTexts } from "@/lib/ki-team-data"

const phases = getKiTeamPhases()

export function HumanApprovalsView() {
  return (
    <section
      aria-labelledby="human-approvals-title"
      className="grid gap-6 xl:grid-cols-[minmax(0,1.1fr)_minmax(22rem,0.9fr)]"
    >
      <div className="rounded-xl border border-border bg-card p-4 sm:p-6">
        <div className="flex items-start gap-3">
          <span className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-status-partial/10 text-status-partial">
            <UserRoundCheck aria-hidden="true" className="size-5" />
          </span>
          <div>
            <h2
              id="human-approvals-title"
              className="font-heading text-lg font-semibold text-foreground"
            >
              Ihre sechs Kontrollpunkte
            </h2>
            <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
              Diese Entscheidungen bleiben entlang des gesamten Ablaufs
              ausdrücklich bei Ihnen.
            </p>
          </div>
        </div>

        <ol className="mt-5 divide-y divide-border">
          {phases.map((phase) => (
            <li
              key={phase.step.step}
              className="grid gap-3 py-4 first:pt-0 last:pb-0 sm:grid-cols-[2.25rem_minmax(0,1fr)]"
            >
              <span className="flex size-8 items-center justify-center rounded-full border border-status-partial/30 bg-status-partial/10 text-sm font-semibold text-status-partial">
                {phase.step.step}
              </span>
              <div>
                <h3 className="text-sm font-semibold text-foreground">
                  {phase.step.label}
                </h3>
                <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
                  {phase.humanAction}
                </p>
              </div>
            </li>
          ))}
        </ol>
      </div>

      <div className="flex flex-col gap-6">
        <section className="rounded-xl border border-border bg-card p-4 sm:p-6">
          <h2 className="flex items-center gap-2 font-heading text-base font-semibold text-foreground">
            <Ban aria-hidden="true" className="size-5 text-muted-foreground" />
            {kiTeamTexts.neverDecides.title}
          </h2>
          <ul className="mt-4 flex flex-col gap-3">
            {kiTeamTexts.neverDecides.points.map((point) => (
              <li key={point} className="flex items-start gap-2 text-sm">
                <XCircle
                  aria-hidden="true"
                  className="mt-0.5 size-4 shrink-0 text-muted-foreground"
                />
                <span>{point}</span>
              </li>
            ))}
          </ul>
        </section>

        <section className="rounded-xl border border-border bg-card p-4 sm:p-6">
          <h2 className="flex items-center gap-2 font-heading text-base font-semibold text-foreground">
            <ShieldCheck
              aria-hidden="true"
              className="size-5 text-muted-foreground"
            />
            {kiTeamTexts.dataProtection.title}
          </h2>
          <ul className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
            {kiTeamTexts.dataProtection.points.map((point) => (
              <li key={point} className="flex items-start gap-2 text-sm">
                <span
                  aria-hidden="true"
                  className="mt-2 size-1.5 shrink-0 rounded-full bg-muted-foreground"
                />
                <span>{point}</span>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </section>
  )
}
