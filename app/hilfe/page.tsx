"use client"

import { AppShell } from "@/components/shell/app-shell"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { ContactForm } from "@/components/contact-form"
import { currentUser, projects, activeProjectId } from "@/lib/mock-data"
import { WORKFLOW_STEPS } from "@/lib/workflow"

// Static help page — no stepper, no search, no contextual help system.
export default function HilfePage() {
  return (
    <AppShell
      user={currentUser}
      projects={projects}
      activeProjectId={activeProjectId}
    >
      <div className="mx-auto max-w-[720px] px-6 py-10">
        <h1 className="mb-8 text-2xl font-semibold text-foreground">Hilfe</h1>

        <section className="mb-8">
          <h2 className="mb-2 text-base font-semibold text-foreground">
            Der Workflow in 6 Schritten
          </h2>
          <p className="mb-3 text-sm leading-relaxed text-muted-foreground">
            Die Plattform führt Sie Schritt für Schritt von der Projektidee bis
            zum fertigen Antragsentwurf. Der aktuelle Schritt ist oben in der
            Schrittleiste markiert.
          </p>
          <ol className="flex list-decimal flex-col gap-1.5 pl-5 text-sm leading-relaxed text-foreground">
            {WORKFLOW_STEPS.map((step) => (
              <li key={step.step}>
                <span className="font-medium">{step.label}</span>
                {" — "}
                <span className="text-muted-foreground">{step.subLabel}</span>
              </li>
            ))}
          </ol>
        </section>

        <section className="mb-8">
          <h2 className="mb-2 text-base font-semibold text-foreground">
            Belege und Prüfungen
          </h2>
          <p className="text-sm leading-relaxed text-muted-foreground">
            Jede Aussage im Antrag kann mit einem Beleg aus Ihren Unterlagen
            verknüpft werden. Das farbige Abzeichen an einem Beleg zeigt, was
            die Plattform automatisch geprüft hat. Das teale Häkchen mit Namen
            zeigt, dass eine Person den Beleg selbst geprüft hat. Beides bleibt
            getrennt sichtbar — die automatische Prüfung ersetzt die
            menschliche nicht, und umgekehrt.
          </p>
        </section>

        <section className="mb-8">
          <h2 className="mb-2 text-base font-semibold text-foreground">
            Analyse, Kosten und automatischer Stopp
          </h2>
          <p className="text-sm leading-relaxed text-muted-foreground">
            Vor jedem Analyse-Durchlauf öffnet sich ein Dialog mit den
            Einstellungen und einer Aufwandsschätzung. Für jeden Durchlauf gilt
            ein Kostenlimit: Wird es erreicht, stoppt der Durchlauf
            automatisch, und bereits erzeugte Ergebnisse bleiben erhalten.
            Dieser automatische Stopp lässt sich nicht abschalten.
          </p>
        </section>

        <section className="mb-8">
          <h2 className="mb-2 text-base font-semibold text-foreground">
            Vertraulichkeitsstufen
          </h2>
          <p className="mb-3 text-sm leading-relaxed text-muted-foreground">
            Die im Intake gewählte Vertraulichkeitsstufe bestimmt, welche
            Dienste die Plattform nutzen darf:
          </p>
          <ul className="flex list-disc flex-col gap-1.5 pl-5 text-sm leading-relaxed text-foreground">
            <li>
              <span className="font-medium">Öffentlich</span>
              {" — "}
              <span className="text-muted-foreground">
                externe KI-Dienste möglich, Webrecherche möglich.
              </span>
            </li>
            <li>
              <span className="font-medium">Intern</span>
              {" — "}
              <span className="text-muted-foreground">
                externe KI-Dienste nur mit Freigabe, Webrecherche bedingt
                möglich.
              </span>
            </li>
            <li>
              <span className="font-medium">Vertraulich</span>
              {" — "}
              <span className="text-muted-foreground">
                Verarbeitung nur lokal — keine externen KI-Dienste, keine
                Webrecherche.
              </span>
            </li>
          </ul>
        </section>

        <p className="mb-8 border-t border-border pt-6 text-sm font-medium text-foreground">
          Die Einreichung erfolgt durch Sie im Innosuisse-Portal.
        </p>

        <section>
          <div className="mb-2 flex items-center justify-between gap-4">
            <h2 className="text-base font-semibold text-foreground">
              Support kontaktieren
            </h2>
            <Dialog>
              <DialogTrigger render={<Button variant="outline" size="sm" />}>
                In Dialog öffnen
              </DialogTrigger>
              <DialogContent className="sm:max-w-md">
                <DialogHeader>
                  <DialogTitle>Support kontaktieren</DialogTitle>
                  <DialogDescription>
                    Schildern Sie Ihr Anliegen — wir melden uns per E-Mail.
                  </DialogDescription>
                </DialogHeader>
                <ContactForm />
              </DialogContent>
            </Dialog>
          </div>
          <Card>
            <CardHeader>
              <CardTitle>Fragen oder Feedback?</CardTitle>
              <CardDescription>
                Schildern Sie Ihr Anliegen — wir melden uns per E-Mail.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ContactForm />
            </CardContent>
          </Card>
        </section>
      </div>
    </AppShell>
  )
}
