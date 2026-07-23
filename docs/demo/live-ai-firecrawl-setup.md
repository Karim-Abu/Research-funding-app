# Live-KI und Firecrawl einrichten

Diese Konfiguration ist nur für öffentliche, synthetische oder nachweislich
anonymisierte Evaluationsfälle vorgesehen. Echte D1/D2-/NDA-Projektdaten dürfen
nicht über direkte Consumer-APIs verarbeitet werden.

## Live-KI

In `backend/.env`:

```dotenv
AGENT_FAKE_PROVIDER=false
AI_EVAL_MODE=real
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
AGENT_MODEL_GPT_56_LUNA_ID=
AGENT_MODEL_GPT_56_TERRA_ID=
AGENT_MODEL_GPT_56_SOL_ID=
AGENT_MODEL_CLAUDE_HAIKU_45_ID=
AGENT_MODEL_CLAUDE_SONNET_5_ID=
AGENT_MODEL_CLAUDE_FABLE_5_ID=
AGENT_MODEL_PRICING_CHF_PER_MILLION={}
```

Nur die tatsächlich verwendeten Routen konfigurieren. Modell-IDs nicht raten:
Es sind ausschließlich die in der Backend-Umgebung gesetzten und per Preflight
bestätigten Provider-Modell-IDs zulässig.

Minimal für `generation_mode=real_eval`: Alle drei Kernrollen
(`CORE_LIVE_ROLE_IDS` = A1 Fakten/Evidenz, A2 Antragstexte, A3 Review) brauchen
je mindestens eine konfigurierte und preflight-bestätigte Route — d. h. neben
Terra (A2) und Sonnet 5 (A3) auch Luna und/oder Haiku 4.5 für A1.

`AGENT_MODEL_PRICING_CHF_PER_MILLION` muss für jede verwendete konkrete
Modell-ID geprüfte CHF-Metadaten enthalten. Erforderliche Felder je Modell-ID:
`input_chf_per_million`, `output_chf_per_million`, `price_version`,
`source_url` und `checked_at`. Diese Dokumentation enthält bewusst keine
Preiswerte oder Secrets.

## Live-Firecrawl

In `backend/.env`:

```dotenv
WEB_RESEARCH_ENABLED=true
WEB_RESEARCH_FAKE_PROVIDER=false
FIRECRAWL_API_KEY=
```

Firecrawl erhält ausschließlich von der Search Query Firewall freigegebene,
public-safe Queries. Rohprojekttext wird nicht gesendet.

## Sicher prüfen

Der Check ist opt-in und verwendet nur konstante synthetische/public-safe
Testdaten:

```powershell
$env:RUN_REAL_PROVIDER_SMOKE = "true"
backend\.venv\Scripts\python.exe scripts\run_provider_preflight.py
```

Ohne Opt-in werden keine externen Aufrufe ausgeführt. Der Bericht enthält nur
Metadaten:

- Route konfiguriert oder nicht
- Preflight-Status
- angefragte und tatsächlich bestätigte Modell-ID
- Firecrawl-Erreichbarkeit und Fehlerklasse
- Latenz und sichere Check-Codes

API-Keys, Prompts, Projekttexte und Rohantworten werden nicht ausgegeben.

Nach einem erfolgreichen Preflight muss ein Live-Lauf im Analyse-Dialog einmalig
bestätigt werden. KI-Ausgaben bleiben Vorschläge und werden nie automatisch
übernommen oder freigegeben.
