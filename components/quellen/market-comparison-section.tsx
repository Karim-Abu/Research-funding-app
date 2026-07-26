"use client"

// "Markt- und Konkurrenzvergleich" — M9I-B. Built only from imported public sources.
// Every shown item is source-backed (verified quote) or marked needs-review /
// insufficient-evidence. No draft is changed; no provider/model/confidence is shown.

import * as React from "react"
import { BarChart3, Loader2 } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { pollOperation } from "@/lib/operations"
import {
  createComparison,
  getLatestComparison,
  MarketComparisonError,
  updateItemStatus,
  ITEM_RELATION_LABELS,
  ITEM_STATUS_LABELS,
  CANDIDATE_TYPE_LABELS,
  CONFIDENCE_LABELS,
  CONFIDENCE_STYLE,
  CENTRALIZATION_LABELS,
  SUPPORT_STATUS_LABELS,
  type ItemStatus,
  type SupportStatus,
  type MarketComparisonDto,
  type MarketComparisonItemDto,
} from "@/lib/market-comparison"
import {
  CANDIDATE_TYPE_ORDER,
  MARKET_TONE_STYLE,
  QUOTE_NOT_CONFIRMED_NOTE,
  candidateTypeOf,
  marketGaps,
  marketPictureFrom,
  marketSummaryCounts,
  marketUiState,
  quoteNeedsConfirmation,
} from "@/lib/market-view"
import { MarketGapList, MarketPictureList } from "@/components/editor/market-blocks"
import { MarketComparisonBasis } from "@/components/editor/market-comparison-basis"
import { cn } from "@/lib/utils"
import type { MarketReadiness } from "@/components/quellen/public-research-panel"

type State = "loading" | "idle" | "generating" | "ready" | "error"

// Empfehlung, KEIN Gate: der Vergleich startet ab 1 geeigneten Quelle; ab 2
// entfällt die Backend-Schwelle «insufficient_external_evidence». Zwei Quellen
// machen einen Vergleich möglich, aber nicht belastbar — das darf die UI nicht
// versprechen (die Aussagekraft bleibt auf den Suchumfang beschränkt).
const RECOMMENDED_ELIGIBLE_SOURCES = 2

function readinessLine(readiness: MarketReadiness): string {
  const n = readiness.eligibleCount
  const count =
    n === 1 ? "1 geeignete Quelle ausgewählt" : `${n} geeignete Quellen ausgewählt`
  if (n >= RECOMMENDED_ELIGIBLE_SOURCES) {
    return `${count} — der Vergleich kann erstellt werden. Seine Aussagekraft bleibt auf die geprüften Quellen beschränkt.`
  }
  if (n === 1) {
    const base = `${count} — mindestens 2 empfohlen, damit der Vergleich mehr als einen Blickwinkel abdeckt`
    if (readiness.nextCandidate?.missingStep === "review") {
      return `${base}. Als Nächstes: «${readiness.nextCandidate.title}» ausdrücklich freigeben (nicht vertrauenswürdiges Inhaltssignal).`
    }
    if (readiness.nextCandidate?.missingStep === "import") {
      return `${base}. Als Nächstes: «${readiness.nextCandidate.title}» übernehmen und prüfen.`
    }
    return `${base}.`
  }
  // n === 0
  if (readiness.nextCandidate?.missingStep === "review") {
    return `Noch keine geeigneten Quellen — als Nächstes: «${readiness.nextCandidate.title}» ausdrücklich freigeben (nicht vertrauenswürdiges Inhaltssignal).`
  }
  if (readiness.nextCandidate?.missingStep === "import") {
    return `Noch keine geeigneten Quellen — als Nächstes: «${readiness.nextCandidate.title}» übernehmen und prüfen.`
  }
  return "Noch keine geeigneten Quellen — rufen Sie zuerst öffentliche Quellen über die Recherche ab."
}

export function MarketComparisonSection({
  projectId,
  sourceNames,
  disabledReason,
  readiness,
}: {
  projectId: string
  // Anzeigenamen der Projektquellen (source_id → Name) für den Abschnitt
  // «Verwendete Quellen» — es werden nie rohe IDs angezeigt.
  sourceNames?: Record<string, string>
  /** Konkreter Grund, warum aktuell kein Vergleich erstellt werden kann —
   *  deaktiviert «Vergleich erstellen» sichtbar statt still. */
  disabledReason?: string | null
  /** Fortschritt Richtung belastbarem Vergleich (2026-07-24) — vom
   *  Research-Panel gemeldet; nie ein hartes Gate, nur Orientierung. */
  readiness?: MarketReadiness | null
}) {
  const [state, setState] = React.useState<State>("loading")
  const [comparison, setComparison] = React.useState<MarketComparisonDto | null>(null)
  const [error, setError] = React.useState<string | null>(null)
  const [expanded, setExpanded] = React.useState(false)
  const pollRef = React.useRef<{ stop: () => void } | null>(null)

  const load = React.useCallback(async () => {
    try {
      const latest = await getLatestComparison(projectId)
      setComparison(latest)
      setState(latest ? "ready" : "idle")
    } catch {
      setState("idle")
    }
  }, [projectId])

  React.useEffect(() => {
    void load()
    return () => pollRef.current?.stop()
  }, [load])

  const generate = React.useCallback(async () => {
    setState("generating")
    setError(null)
    try {
      const accepted = await createComparison(projectId)
      pollRef.current = pollOperation(accepted.operation_id, {
        onTerminal: async (op) => {
          if (op.status !== "succeeded") {
            setState("error")
            setError("Der Vergleich konnte nicht erstellt werden.")
            return
          }
          await load()
        },
      })
    } catch (err) {
      setState("error")
      setError(
        err instanceof MarketComparisonError
          ? err.message
          : "Es ist ein Fehler aufgetreten."
      )
    }
  }, [projectId, load])

  const setItemStatus = React.useCallback(
    async (itemId: string, status: ItemStatus, supportStatus?: SupportStatus) => {
      try {
        await updateItemStatus(itemId, status, supportStatus)
        await load()
      } catch {
        // keep the current view on transient errors
      }
    },
    [load]
  )

  // Strikte Trennung: Marktaussagen (Marktgrösse, Kundenprobleme) sind KEINE
  // Lösungskandidaten und dürfen nie in der Anbieter-/Alternativen-Tabelle stehen.
  const marketClaims = (comparison?.items ?? []).filter(
    (item) => candidateTypeOf(item) === null
  )
  const solutions = (comparison?.items ?? []).filter(
    (item) => candidateTypeOf(item) !== null
  )
  // Marktbild ausschliesslich aus den Backend-Marktdaten — keine aus Lösungen
  // abgeleiteten Ersatzpunkte, sonst entsteht wieder die Vermischung.
  const picturePoints = comparison?.market_picture
    ? marketPictureFrom(comparison).points
    : []
  const basis = comparison?.comparison_basis
  const counts = marketSummaryCounts(comparison)
  // Der Vergleich bezieht sich auf die Quellen seines Erstellungszeitpunkts.
  // Kommen danach geprüfte Quellen dazu, ist nicht «mehr Evidenz vorhanden»,
  // sondern «der Vergleich kennt sie noch nicht» die ehrliche Aussage.
  const usedSourceCount = comparison?.source_version_ids?.length ?? 0
  const unusedSourceCount =
    readiness && usedSourceCount > 0
      ? Math.max(0, readiness.eligibleCount - usedSourceCount)
      : 0
  // Die EINE Statuswahrheit dieser Oberfläche.
  const ui = marketUiState(comparison, { unusedSourceCount })

  return (
    <section
      data-testid="market-comparison-section"
      className="rounded-lg border border-border bg-card p-5"
    >
      <div className="mb-1 flex items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <BarChart3 className="size-4 text-muted-foreground" />
          <h3 className="text-sm font-semibold text-foreground">
            Markt- und Konkurrenzvergleich
          </h3>
          {/* Die einzige Statusaussage der Oberfläche (identisch zu Rail + Sheet). */}
          {comparison && (
            <Badge
              variant="outline"
              data-testid="market-comparison-status"
              className={cn("border-transparent", MARKET_TONE_STYLE[ui.tone])}
            >
              {ui.label}
            </Badge>
          )}
        </div>
        <Button
          type="button"
          size="sm"
          variant="outline"
          disabled={state === "generating" || Boolean(disabledReason)}
          onClick={generate}
        >
          {state === "generating" ? (
            <>
              <Loader2 className="size-4 animate-spin" /> Wird erstellt …
            </>
          ) : comparison ? (
            "Neu erstellen"
          ) : (
            "Vergleich erstellen"
          )}
        </Button>
      </div>
      <p className="mb-3 text-xs text-muted-foreground">
        Nur aus geprüften öffentlichen Quellen — kein automatischer Eintrag in
        den Antrag.
      </p>

      {/* Verglichen mit — eine Zeile statt der vollen Vergleichsbasis-Karte;
          die volle Karte steht unter «Details öffnen». */}
      {basis && (
        <p className="mb-3 text-xs text-muted-foreground" data-testid="market-comparison-basis-line">
          Verglichen mit: <span className="font-medium text-foreground">{basis.title}</span>
          {basis.innovation_field ? ` · ${basis.innovation_field}` : ""}
        </p>
      )}

      {/* EINE Antwort: Ergebnis, Suchumfang, nächster Schritt. Ersetzt die
          früher nebeneinanderstehenden Blöcke (Gesamturteil, Veraltung,
          Limitationshinweise, Fortschrittszeile, Leerzustand). */}
      <div
        data-testid="market-section-judgment"
        className="mb-3 rounded-md border border-border bg-muted/20 px-3 py-2.5"
      >
        <p className="text-xs text-foreground">{ui.summary}</p>
        {comparison?.competition_judgment && (
          <p className="mt-0.5 text-[11px] text-muted-foreground">
            {comparison.competition_judgment.scope_summary}
          </p>
        )}
        <p className="mt-1 text-[11px] text-muted-foreground" data-testid="market-section-next-step">
          Nächster Schritt: {ui.nextStep}
        </p>
      </div>

      {/* Vor dem ersten Vergleich zeigt die Fortschrittszeile, wie weit die
          Quellenauswahl ist. Sobald ein Vergleich vorliegt, gilt allein der
          Status oben — sonst stünde «kann erstellt werden» neben «reicht nicht». */}
      {!comparison && readiness && (readiness.totalImported > 0 || readiness.eligibleCount > 0) && (
        <p
          className="mb-3 text-xs font-medium text-foreground"
          data-testid="market-comparison-readiness"
        >
          {readinessLine(readiness)}
        </p>
      )}
      {disabledReason && (
        <p
          className="mb-3 text-xs text-muted-foreground"
          data-testid="market-comparison-disabled-reason"
        >
          {disabledReason}
        </p>
      )}

      {error && (
        <p role="alert" className="mb-3 text-sm text-destructive">
          {error}
        </p>
      )}

      {/* Was noch fehlt — die eine Lückenliste, immer sichtbar. */}
      <MarketGapList
        gaps={marketGaps(comparison)}
        limit={3}
        testId="market-research-gaps"
      />

      {/* Eine Hauptaktion je Zustand; Details nur bei Bedarf. Vergleichsbasis,
          Lösungslandschaft, Marktaussagen, Konsequenzen und Quellenliste stehen
          hinter «Details öffnen». */}
      <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-border pt-3">
        {(ui.status === "research_needed" || ui.status === "not_started") && (
          <Button
            type="button"
            size="sm"
            variant="outline"
            render={<a href="#public-research-panel" />}
            nativeButton={false}
          >
            Recherche ergänzen
          </Button>
        )}
        {comparison && (
          <Button
            type="button"
            size="sm"
            variant="ghost"
            aria-expanded={expanded}
            aria-controls="market-comparison-details"
            onClick={() => setExpanded((value) => !value)}
          >
            {expanded ? "Details schliessen" : "Details öffnen"}
          </Button>
        )}
      </div>

      {expanded && comparison && (
        <div
          id="market-comparison-details"
          data-testid="market-comparison-details"
          className="mt-3 flex flex-col gap-4"
        >
          {comparison.comparison_basis && (
            <MarketComparisonBasis basis={comparison.comparison_basis} />
          )}

          {/* Sektion A — Marktbild (Marktinformationen, klar getrennt von den Lösungen unten). */}
          {(picturePoints.length > 0 || marketClaims.length > 0) && (
            <div data-testid="market-section-picture" className="rounded-md border border-border bg-muted/20 px-3 py-2.5">
              <p className="text-xs font-semibold text-foreground">Marktbild</p>
              <p className="mb-1 text-[11px] text-muted-foreground">
                Marktinformationen — keine Wettbewerber.
              </p>
              <MarketPictureList points={picturePoints} />
              {/* Marktaussagen bleiben prüfbar — nur eben nicht als «Anbieter». */}
              {marketClaims.length > 0 && (
                <details className="mt-2" data-testid="market-claims-review">
                  <summary className="cursor-pointer text-xs font-medium text-foreground">
                    Marktaussagen prüfen ({marketClaims.length})
                  </summary>
                  <ul className="mt-2 flex flex-col gap-2">
                    {marketClaims.map((item) => (
                      <MarketClaimRow
                        key={item.item_id}
                        item={item}
                        onSetStatus={setItemStatus}
                      />
                    ))}
                  </ul>
                </details>
              )}
            </div>
          )}

          {/* Sektion B — Lösungslandschaft: die eigentliche Vergleichstabelle,
              gruppiert nach Lösungsart. Enthält nie Marktstatistiken. */}
          {comparison.items.length > 0 && (
            <div className="overflow-x-auto" data-testid="market-comparison-table">
              <p className="mb-1 text-xs font-semibold text-foreground">Lösungslandschaft</p>
              <p className="mb-2 text-[11px] text-muted-foreground">
                Gefundene Lösungen und Alternativen, gruppiert nach Art — verglichen mit
                der Vergleichsbasis oben.
              </p>
              {solutions.length === 0 && (
                <p className="text-xs text-status-partial" role="status">
                  Im Suchumfang wurden bisher nur Marktaussagen gefunden, aber keine
                  vergleichbaren Lösungen. Die offenen Evidenzlücken unten zeigen, was fehlt.
                </p>
              )}
              {CANDIDATE_TYPE_ORDER.map((type) => {
                const items = solutions.filter((i) => candidateTypeOf(i) === type)
                if (items.length === 0) return null
                return (
                  <div key={type} className="mb-4 last:mb-0">
                    <p className="mb-1 text-xs font-medium text-foreground">
                      {CANDIDATE_TYPE_LABELS[type]} ({items.length})
                    </p>
                    <table className="w-full border-collapse text-left text-xs">
                      <thead>
                        <tr className="border-b border-border text-muted-foreground">
                          <th className="py-2 pr-3 font-medium">Anbieter/Alternative</th>
                          <th className="py-2 pr-3 font-medium">Zielgruppe</th>
                          <th className="py-2 pr-3 font-medium">Kernnutzen</th>
                          <th className="py-2 pr-3 font-medium">Differenzierung</th>
                          <th className="py-2 pr-3 font-medium">Geschäftsmodell</th>
                          <th className="py-2 pr-3 font-medium">Schweiz-Relevanz</th>
                          <th className="py-2 pr-3 font-medium">Belege</th>
                          <th className="py-2 pr-3 font-medium">Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        {items.map((item) => (
                          <ItemRow
                            key={item.item_id}
                            item={item}
                            onSetStatus={setItemStatus}
                          />
                        ))}
                      </tbody>
                    </table>
                  </div>
                )
              })}
            </div>
          )}

          {/* RUN 4A: höchstens fünf konkrete Konsequenzen für den Antrag. */}
          {(comparison.consequences?.length ?? 0) > 0 && (
            <div data-testid="market-consequences">
              <p className="text-xs font-medium text-foreground">
                Was das für den Antrag bedeutet
              </p>
              <ul className="mt-1 list-disc pl-5 text-xs text-muted-foreground">
                {(comparison.consequences ?? []).slice(0, 5).map((entry, i) => (
                  <li key={i}>{entry}</li>
                ))}
              </ul>
            </div>
          )}

          {comparison.items.some((i) => i.source_document_ids.length > 0) && (
            <div data-testid="market-used-sources">
              <p className="text-xs font-medium text-foreground">Verwendete Quellen</p>
              <ul className="mt-1 list-disc pl-5 text-xs text-muted-foreground">
                {usedSourceNames(comparison, sourceNames).map((name, i) => (
                  <li key={i}>{name}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </section>
  )
}

function usedSourceNames(
  comparison: MarketComparisonDto,
  sourceNames?: Record<string, string>
): string[] {
  const ids = new Set<string>()
  for (const item of comparison.items) {
    for (const id of item.source_document_ids) ids.add(id)
  }
  // Nie rohe IDs anzeigen: unbekannte Quellen erscheinen als generischer Eintrag.
  const names = new Set<string>()
  for (const id of ids) {
    names.add(sourceNames?.[id] ?? "Importierte öffentliche Quelle")
  }
  return [...names].sort((a, b) => a.localeCompare(b, "de"))
}

function ItemRow({
  item,
  onSetStatus,
}: {
  item: MarketComparisonItemDto
  onSetStatus: (itemId: string, status: ItemStatus, supportStatus?: SupportStatus) => void
}) {
  return (
    <tr className="border-b border-border/60 align-top">
      <td className="py-2 pr-3 font-medium text-foreground">
        {item.name}
        {/* Die Lösungsart steht bereits im Gruppentitel — hier nur der Bezug
            zum eigenen Projekt und die belegten Überschneidungen. */}
        <span className="block text-[11px] font-normal text-muted-foreground">
          {ITEM_RELATION_LABELS[item.relation_to_project]}
        </span>
        {(item.overlaps?.length ?? 0) > 0 && (
          <span className="block text-[11px] font-normal text-muted-foreground">
            Überschneidungen: {item.overlaps?.join(" · ")}
          </span>
        )}
        {/* RUN 4A: sekundäre Vergleichsdimensionen progressiv statt als
            eigene, immer sichtbare Spalte. */}
        <details className="mt-1 text-[11px] font-normal text-muted-foreground">
          <summary className="cursor-pointer">Weitere Details</summary>
          <dl className="mt-1 grid grid-cols-[auto_1fr] gap-x-2">
            <dt>Kurzbeschreibung</dt><dd>{item.description ?? "—"}</dd>
            <dt>Lösungstyp</dt><dd>{item.solution_type ?? "—"}</dd>
            <dt>Zentralität</dt><dd>{CENTRALIZATION_LABELS[item.centralization ?? "unclear"]}</dd>
            <dt>Daten/Zugriff</dt><dd>{item.data_access_model ?? "—"}</dd>
            <dt>Funktionen</dt><dd>{item.relevant_functions?.join(", ") || "nicht öffentlich belegt"}</dd>
          </dl>
        </details>
      </td>
      <td className="py-2 pr-3 text-muted-foreground">
        {item.target_customer_segment ?? "nicht öffentlich belegt"}
      </td>
      <td className="py-2 pr-3 text-muted-foreground">
        {item.core_problem_or_benefit ?? item.description ?? "—"}
      </td>
      <td className="py-2 pr-3 text-muted-foreground">
        {item.differentiation_relevance?.trim() || "nicht öffentlich belegt"}
      </td>
      <td className="py-2 pr-3 text-muted-foreground">
        {item.price_business_model ?? "nicht öffentlich belegt"}
      </td>
      <td className="py-2 pr-3 text-muted-foreground">
        {item.swiss_relevance ?? "unbestätigt"}
      </td>
      <td className="py-2 pr-3">
        {item.evidence_quotes.length > 0 ? (
          <blockquote className="border-l-2 border-border pl-2 text-[11px] italic text-muted-foreground">
            „{item.evidence_quotes[0].quote}“
          </blockquote>
        ) : (
          <span className="text-[11px] text-muted-foreground">Kein belegtes Zitat</span>
        )}
        {item.evidence_quotes[0]?.source_url && (
          <a href={item.evidence_quotes[0].source_url} target="_blank" rel="noreferrer" className="mt-1 block break-all text-[11px] text-primary hover:underline">
            Quelle öffnen
          </a>
        )}
      </td>
      <td className="py-2 pr-3">
        <EvidenceStatus item={item} />
        <ReviewActions item={item} onSetStatus={onSetStatus} />
      </td>
    </tr>
  )
}

/**
 * Ein exaktes Zitat belegt eine Fundstelle, nicht die fachliche Richtigkeit —
 * beides wird getrennt und ausgeschrieben (CLAUDEX §6, kein «Textstelle
 * gefunden» als scheinbare Bestätigung).
 */
function EvidenceStatus({ item }: { item: MarketComparisonItemDto }) {
  return (
    <>
      <Badge variant="secondary" className={CONFIDENCE_STYLE[item.confidence_label]}>
        {item.status === "accepted"
          ? ITEM_STATUS_LABELS.accepted
          : CONFIDENCE_LABELS[item.confidence_label]}
      </Badge>
      {item.status !== "accepted" && quoteNeedsConfirmation(item) && (
        <p className="mt-1 text-[11px] text-status-partial">{QUOTE_NOT_CONFIRMED_NOTE}</p>
      )}
      <p className="mt-1 text-[11px] text-muted-foreground">
        Fundstelle: {item.coverage_status === "exact_quote_verified" ? "exakt gefunden" : "ungeprüft"}
        {" · "}Inhalt: {SUPPORT_STATUS_LABELS[item.support_status ?? "unreviewed"]}
      </p>
    </>
  )
}

/** RUN 4A A11y: Aktionen pro Eintrag eindeutig benennen (Screenreader hören
 *  sonst nur mehrfach «Übernehmen»/«Prüfen»). */
function ReviewActions({
  item,
  onSetStatus,
}: {
  item: MarketComparisonItemDto
  onSetStatus: (itemId: string, status: ItemStatus, supportStatus?: SupportStatus) => void
}) {
  return (
    <>
      <div className="mt-1 flex gap-1">
        <button
          type="button"
          aria-label={`${item.name}: Übernehmen`}
          className="rounded text-[11px] text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          onClick={() => onSetStatus(item.item_id, "accepted")}
        >
          Übernehmen
        </button>
        <span aria-hidden className="text-[11px] text-muted-foreground">·</span>
        <button
          type="button"
          aria-label={`${item.name}: Prüfen`}
          className="rounded text-[11px] text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          onClick={() => onSetStatus(item.item_id, "needs_human_review")}
        >
          Prüfen
        </button>
      </div>
      <div className="mt-1 flex flex-wrap gap-1">
        <button type="button" aria-label={`${item.name}: Stützt`} className="rounded text-[11px] text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" onClick={() => onSetStatus(item.item_id, item.status, "supports")}>Stützt</button>
        <button type="button" aria-label={`${item.name}: Stützt teilweise`} className="rounded text-[11px] text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" onClick={() => onSetStatus(item.item_id, item.status, "partial")}>Teilweise</button>
        <button type="button" aria-label={`${item.name}: Stützt nicht`} className="rounded text-[11px] text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" onClick={() => onSetStatus(item.item_id, item.status, "does_not_support")}>Stützt nicht</button>
      </div>
    </>
  )
}

/**
 * Marktaussage (Marktgrösse, Kundenproblem) — bleibt vollständig prüfbar, wird
 * aber nie als Anbieter/Alternative dargestellt.
 */
function MarketClaimRow({
  item,
  onSetStatus,
}: {
  item: MarketComparisonItemDto
  onSetStatus: (itemId: string, status: ItemStatus, supportStatus?: SupportStatus) => void
}) {
  return (
    <li className="rounded-md border border-border bg-card px-3 py-2">
      <p className="text-xs font-medium text-foreground">{item.name}</p>
      {item.description && (
        <p className="text-[11px] text-muted-foreground">{item.description}</p>
      )}
      {item.evidence_quotes.length > 0 && (
        <blockquote className="mt-1 border-l-2 border-border pl-2 text-[11px] italic text-muted-foreground">
          „{item.evidence_quotes[0].quote}“
        </blockquote>
      )}
      {item.evidence_quotes[0]?.source_url && (
        <a
          href={item.evidence_quotes[0].source_url}
          target="_blank"
          rel="noreferrer"
          className="mt-1 block break-all text-[11px] text-primary hover:underline"
        >
          Quelle öffnen
        </a>
      )}
      <div className="mt-1">
        <EvidenceStatus item={item} />
        <ReviewActions item={item} onSetStatus={onSetStatus} />
      </div>
    </li>
  )
}
