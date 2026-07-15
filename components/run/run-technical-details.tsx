"use client"

import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion"
import type { RunTechnicalSummaryDto } from "@/lib/runs"

// Deutsche Kurznamen der Agentenrollen (Katalog aus lib/ki-team-data).
const AGENT_LABELS: Record<string, string> = {
  A1: "Fakten-Leser (A1)",
  A2: "Text-Vorschlager (A2)",
  A3: "Prüf-Zusammenfasser (A3)",
}

/** Eingeklappte technische Angaben nach dem Lauf (CLAUDEX: technische Details
 *  nur unter «Technische Details»): Provider, Modell, Tokens, Kosten, Latenz,
 *  Run-ID — alles echte Werte aus AgentInvocations/UsageRecords. */
export function RunTechnicalDetails({
  technical,
}: {
  technical: RunTechnicalSummaryDto
}) {
  return (
    <Accordion className="rounded-lg border border-border px-4">
      <AccordionItem value="technical">
        <AccordionTrigger className="text-sm font-medium">
          Technische Details
        </AccordionTrigger>
        <AccordionContent>
          <div className="flex flex-col gap-3 pb-2 text-xs text-muted-foreground">
            {!technical.model_called ? (
              <p>Kein Modellaufruf.</p>
            ) : technical.agents.length === 0 ? (
              <p>Keine Modellmetadaten vorhanden.</p>
            ) : (
              <ul className="flex flex-col gap-2">
                {technical.agents.map((agent) => (
                  <li key={agent.agent_id} className="flex flex-col gap-0.5">
                    <span className="font-medium text-foreground">
                      {AGENT_LABELS[agent.agent_id] ?? agent.agent_id}
                    </span>
                    <span>
                      Provider: {agent.providers.join(", ") || "—"} · Modell:{" "}
                      {agent.models.join(", ") || "—"} · Aufrufe:{" "}
                      {agent.invocations}
                    </span>
                    <span>
                      Tatsächlich gemeldet: {agent.actual_models?.join(", ") || "—"}
                      {agent.skill_versions?.length
                        ? ` · Skill-Version: ${agent.skill_versions.join(", ")}`
                        : ""}
                    </span>
                    <span>
                      Tokens: {agent.input_tokens} ein / {agent.output_tokens}{" "}
                      aus · Kosten:{" "}
                      {agent.priced_cost_chf > 0
                        ? `CHF ${agent.priced_cost_chf.toFixed(4)}`
                        : agent.has_unpriced_usage
                          ? "nicht bepreist"
                          : "keine externen Kosten"}{" "}
                      · Latenz: {agent.latency_ms_total} ms
                    </span>
                    <span>
                      Retries: {agent.retry_count ?? 0} · Beendigung:{" "}
                      {agent.termination_reasons?.join(", ") || "—"}
                    </span>
                    {agent.attempts && agent.attempts.length > 0 && (
                      <details className="mt-1">
                        <summary className="cursor-pointer">Versuche anzeigen</summary>
                        <ul className="mt-1 flex flex-col gap-1 pl-3">
                          {agent.attempts.map((attempt, index) => (
                            <li key={`${attempt.route_alias}:${index}`}>
                              {attempt.route_alias} · {attempt.provider} · angefragt:{" "}
                              {attempt.requested_model_id ?? "—"} · tatsächlich:{" "}
                              {attempt.actual_model_id ?? "—"} · {attempt.status}
                              {attempt.retry_index ? ` · Retry ${attempt.retry_index}` : ""}
                              {attempt.error_class ? ` · ${attempt.error_class}` : ""}
                              {attempt.cost_status
                                ? ` · ${attempt.input_tokens ?? 0}/${attempt.output_tokens ?? 0} Tokens · ${attempt.cost_status}`
                                : ""}
                              {attempt.estimated_cost_status
                                ? ` · Schätzung: ${attempt.estimated_cost_status}${attempt.estimated_cost_chf != null ? ` (CHF ${attempt.estimated_cost_chf.toFixed(4)})` : ""}`
                                : ""}
                            </li>
                          ))}
                        </ul>
                      </details>
                    )}
                  </li>
                ))}
              </ul>
            )}
            {technical.same_provider_a2_a3 === true && (
              <p>
                Hinweis: Textvorschläge (A2) und Qualitätsprüfung (A3) liefen
                über denselben Dienst — die Prüfung ist damit keine unabhängige
                Zweitmeinung.
              </p>
            )}
            {technical.has_unpriced_usage && (
              <p>
                Einzelne Aufrufe sind nicht bepreist — die Kostensumme ist
                deshalb eine Untergrenze, nie «gratis».
              </p>
            )}
            <p>
              Run-ID: <code className="text-foreground">{technical.run_id}</code>
            </p>
          </div>
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  )
}
