"use client"

import { AlertTriangle, Check, Minus } from "lucide-react"
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion"
import { Separator } from "@/components/ui/separator"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { RunStatusBadge } from "@/components/kosten/run-status-badge"
import {
  COST_STATUS_LABELS,
  EXECUTION_STATUS_LABELS,
  RUN_TYPE_LABELS,
  executionLatencyTotal,
  formatCost,
  formatDateTime,
  formatDuration,
  formatTokens,
  getRunDurationMs,
  runProviderModelLabel,
  type KostenRunViewModel,
  type ModelExecutionViewModel,
} from "@/lib/kosten"
import { cn } from "@/lib/utils"

interface RunDetailDrawerProps {
  run: KostenRunViewModel | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

function DetailItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 rounded-md border border-border/70 bg-muted/20 px-3 py-2.5">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="mt-0.5 break-words text-sm font-medium text-foreground tabular-nums">
        {value}
      </dd>
    </div>
  )
}

function ToggleValue({ enabled }: { enabled: boolean }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      {enabled ? (
        <Check aria-hidden className="size-3.5 text-status-fulfilled" />
      ) : (
        <Minus aria-hidden className="size-3.5 text-muted-foreground" />
      )}
      {enabled ? "Aktiv" : "Nicht aktiv"}
    </span>
  )
}

function ExecutionCard({ execution }: { execution: ModelExecutionViewModel }) {
  return (
    <li className="rounded-lg border border-border px-4 py-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="text-sm font-semibold text-foreground">
            {execution.roleLabel}
          </p>
          <p className="text-xs text-muted-foreground">
            {execution.provider} / {execution.model}
          </p>
        </div>
        {execution.status && (
          <span
            className={cn(
              "text-xs font-medium",
              execution.status === "completed"
                ? "text-status-fulfilled"
                : execution.status === "failed"
                  ? "text-destructive"
                  : "text-muted-foreground"
            )}
          >
            {EXECUTION_STATUS_LABELS[execution.status]}
          </span>
        )}
      </div>
      <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 text-xs sm:grid-cols-3">
        <div>
          <dt className="text-muted-foreground">Aufrufe</dt>
          <dd className="mt-0.5 font-medium tabular-nums">
            {execution.callCount ?? "Nicht verfügbar"}
          </dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Tokens ein / aus</dt>
          <dd className="mt-0.5 font-medium tabular-nums">
            {formatTokens(execution.inputTokens)} / {formatTokens(execution.outputTokens)}
          </dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Kosten</dt>
          <dd className="mt-0.5 font-medium tabular-nums">
            {formatCost(execution.cost)}
          </dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Gesamtlatenz</dt>
          <dd className="mt-0.5 font-medium tabular-nums">
            {formatDuration(execution.latencyMsTotal)}
          </dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Retries</dt>
          <dd className="mt-0.5 font-medium tabular-nums">
            {execution.retryCount ?? "Nicht verfügbar"}
          </dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Kostenstatus</dt>
          <dd className="mt-0.5 font-medium">
            {COST_STATUS_LABELS[execution.cost?.status ?? "unavailable"]}
          </dd>
        </div>
      </dl>
    </li>
  )
}

function TechnicalDetails({ executions }: { executions: ModelExecutionViewModel[] }) {
  const hasDetails = executions.some(
    (execution) =>
      execution.generationKinds?.length ||
      execution.promptVersions?.length ||
      execution.skillVersions?.length ||
      execution.terminationReasons?.length ||
      execution.attempts?.length
  )

  return (
    <Accordion className="rounded-lg border border-border px-4">
      <AccordionItem value="technical">
        <AccordionTrigger>Technische Details</AccordionTrigger>
        <AccordionContent>
          {!hasDetails ? (
            <p className="pb-2 text-xs text-muted-foreground">
              Keine zusätzlichen technischen Metadaten vorhanden.
            </p>
          ) : (
            <ul className="flex flex-col gap-3 pb-2">
              {executions.map((execution) => {
                const hasExecutionDetails =
                  execution.generationKinds?.length ||
                  execution.promptVersions?.length ||
                  execution.skillVersions?.length ||
                  execution.terminationReasons?.length ||
                  execution.attempts?.length
                if (!hasExecutionDetails) return null
                return (
                  <li key={execution.id} className="text-xs text-muted-foreground">
                    <p className="font-medium text-foreground">
                      {execution.roleLabel}
                    </p>
                    {execution.generationKinds?.length ? (
                      <p>Ausführungsart: {execution.generationKinds.join(", ")}</p>
                    ) : null}
                    {execution.promptVersions?.length ? (
                      <p>Prompt-Version: {execution.promptVersions.join(", ")}</p>
                    ) : null}
                    {execution.skillVersions?.length ? (
                      <p>Skill-Version: {execution.skillVersions.join(", ")}</p>
                    ) : null}
                    {execution.terminationReasons?.length ? (
                      <p>Beendigung: {execution.terminationReasons.join(", ")}</p>
                    ) : null}
                    {execution.attempts?.length ? (
                      <details className="mt-1.5">
                        <summary className="cursor-pointer rounded outline-none focus-visible:ring-2 focus-visible:ring-ring">
                          Versuche anzeigen
                        </summary>
                        <ul className="mt-2 flex flex-col gap-2 border-l border-border pl-3">
                          {execution.attempts.map((attempt) => (
                            <li key={attempt.id}>
                              <p className="font-medium text-foreground">
                                {attempt.provider} · {EXECUTION_STATUS_LABELS[attempt.status]}
                              </p>
                              <p>
                                Angefragt: {attempt.requestedModel ?? "Nicht verfügbar"} ·
                                Tatsächlich: {attempt.actualModel ?? "Nicht verfügbar"}
                              </p>
                              <p>
                                Versuch {attempt.retryIndex + 1} · Latenz:{" "}
                                {formatDuration(attempt.latencyMs)} · Kosten:{" "}
                                {formatCost(attempt.cost)}
                              </p>
                            </li>
                          ))}
                        </ul>
                      </details>
                    ) : null}
                  </li>
                )
              })}
            </ul>
          )}
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  )
}

export function RunDetailDrawer({
  run,
  open,
  onOpenChange,
}: RunDetailDrawerProps) {
  if (!run) return null

  const modelLatency = executionLatencyTotal(run.executions)

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        className="w-full gap-0 overflow-y-auto p-0 sm:max-w-xl lg:max-w-2xl"
      >
        <SheetHeader className="border-b border-border px-5 py-5 sm:px-6">
          <div className="flex flex-wrap items-start justify-between gap-3 pr-8">
            <div>
              <SheetTitle>{RUN_TYPE_LABELS[run.type]}</SheetTitle>
              <SheetDescription>
                {formatDateTime(run.startedAt)} · {run.user}
              </SheetDescription>
            </div>
            <RunStatusBadge status={run.status} />
          </div>
        </SheetHeader>

        <div className="flex flex-col gap-6 px-5 py-5 sm:px-6">
          <section aria-labelledby="run-overview-heading">
            <h3 id="run-overview-heading" className="text-sm font-semibold">
              Übersicht
            </h3>
            <dl className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
              <DetailItem label="Laufzeit" value={formatDuration(getRunDurationMs(run))} />
              <DetailItem label="Kosten" value={formatCost(run.cost)} />
              <DetailItem label="Provider / Modell" value={runProviderModelLabel(run)} />
              <div className="rounded-md border border-border/70 bg-muted/20 px-3 py-2.5">
                <dt className="text-xs text-muted-foreground">KI-Unterstützung</dt>
                <dd className="mt-0.5 text-sm font-medium"><ToggleValue enabled={run.kiEnabled} /></dd>
              </div>
              <div className="rounded-md border border-border/70 bg-muted/20 px-3 py-2.5">
                <dt className="text-xs text-muted-foreground">Webrecherche</dt>
                <dd className="mt-0.5 text-sm font-medium"><ToggleValue enabled={run.webEnabled} /></dd>
              </div>
              <DetailItem
                label="Kostenstatus"
                value={COST_STATUS_LABELS[run.cost.status]}
              />
            </dl>
          </section>

          <Separator />

          <section aria-labelledby="run-cost-latency-heading">
            <h3 id="run-cost-latency-heading" className="text-sm font-semibold">
              Kosten &amp; Laufzeit
            </h3>
            <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-3 text-sm sm:grid-cols-3">
              <div>
                <dt className="text-xs text-muted-foreground">LLM-Aufrufe</dt>
                <dd className="mt-0.5 font-medium tabular-nums">{run.llmCalls ?? "Nicht verfügbar"}</dd>
              </div>
              <div>
                <dt className="text-xs text-muted-foreground">Web-Aufrufe</dt>
                <dd className="mt-0.5 font-medium tabular-nums">{run.webCalls ?? "Nicht verfügbar"}</dd>
              </div>
              <div>
                <dt className="text-xs text-muted-foreground">Modelllatenz gesamt</dt>
                <dd className="mt-0.5 font-medium tabular-nums">{formatDuration(modelLatency)}</dd>
              </div>
              <div>
                <dt className="text-xs text-muted-foreground">Input-Tokens</dt>
                <dd className="mt-0.5 font-medium tabular-nums">{formatTokens(run.inputTokens)}</dd>
              </div>
              <div>
                <dt className="text-xs text-muted-foreground">Output-Tokens</dt>
                <dd className="mt-0.5 font-medium tabular-nums">{formatTokens(run.outputTokens)}</dd>
              </div>
            </dl>
            <p className="mt-3 text-xs text-muted-foreground">
              Die Run-Laufzeit misst Start bis Ende. Modelllatenzen stammen aus
              den gemeldeten technischen Ausführungen und ersetzen keine fehlende Run-Laufzeit.
            </p>
          </section>

          {run.executions.length > 0 && (
            <>
              <Separator />
              <section aria-labelledby="run-executions-heading">
                <h3 id="run-executions-heading" className="text-sm font-semibold">
                  Agenten &amp; technische Ausführung
                </h3>
                <ul className="mt-3 flex flex-col gap-2">
                  {run.executions.map((execution) => (
                    <ExecutionCard key={execution.id} execution={execution} />
                  ))}
                </ul>
              </section>
            </>
          )}

          {run.stopReason && (
            <div
              role={run.status === "failed" ? "alert" : "note"}
              className={cn(
                "flex items-start gap-2 rounded-lg border px-4 py-3",
                run.status === "failed"
                  ? "border-destructive/30 bg-destructive/5"
                  : "border-status-partial/30 bg-status-partial/5"
              )}
            >
              <AlertTriangle
                aria-hidden
                className={cn(
                  "mt-0.5 size-4 shrink-0",
                  run.status === "failed" ? "text-destructive" : "text-status-partial"
                )}
              />
              <div>
                <p className="text-sm font-medium">
                  {run.status === "failed" ? "Fehlergrund" : "Stop-Grund"}
                </p>
                <p className="mt-0.5 text-sm text-foreground">{run.stopReason}</p>
              </div>
            </div>
          )}

          <Separator />

          <section aria-labelledby="run-audit-heading">
            <h3 id="run-audit-heading" className="text-sm font-semibold">Audit</h3>
            {run.auditRef ? (
              <div className="mt-2">
                <p className="text-sm text-foreground">
                  Audit-Referenz: <span className="font-medium">{run.auditRef}</span>
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Der Durchlauf ist mit dieser Referenz nachvollziehbar dokumentiert.
                </p>
              </div>
            ) : (
              <p className="mt-2 text-sm text-muted-foreground">
                Keine Audit-Referenz verfügbar.
              </p>
            )}
          </section>

          <TechnicalDetails executions={run.executions} />
        </div>
      </SheetContent>
    </Sheet>
  )
}
