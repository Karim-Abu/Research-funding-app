# Verifikationsbericht zur Bedienungsanleitung «Innosuisse-Antrag»

Dieser Bericht dokumentiert, was für [`SCHNELLSTART.md`](SCHNELLSTART.md) und
[`BEDIENUNGSANLEITUNG.md`](BEDIENUNGSANLEITUNG.md) tatsächlich ausgeführt wurde,
mit welchem Ergebnis, und was ausdrücklich **nicht** geprüft wurde. Er richtet
sich an technische Leserinnen und Leser sowie an die Prüfung der Arbeit.

Er beschreibt einen abgeschlossenen Prüfstand. Wird die Dokumentation später
geändert, ist dieser Bericht neu zu erheben.

## 1 Geprüfter Stand

| Angabe | Wert |
|---|---|
| **Geprüfter Software- und Dokumentationsstand** | `e005570372e7a68887053e052257d48b89ac0a15` — Commit «docs: Bedienungsdokumentation für externe Nutzung überarbeiten» |
| **Commit dieses Verifikationsberichts** | der unmittelbar folgende Dokumentationscommit, der diese Datei hinzufügt |
| Branch | `stabilize/eval3-final-01` |
| Working-Tree während des Prüflaufs | sauber bis auf die erzeugten Nachweisdateien unter `docs/evaluation/doku-verifikation-2026-08-05/` und diesen Bericht |
| Prüfdatum | 5. August 2026 |
| Betriebssystem | Windows 11 Pro, Build 10.0.26200 |
| Shell | Windows PowerShell 5.1 |
| Git | 2.50.1.windows.1 |
| Node.js | 24.16.0 |
| pnpm | 11.5.3 (über Corepack; das Repository fixiert keine Version, `pnpm-lock.yaml` verlangt Format `9.0`) |
| Python | 3.13.6 (System und `backend\.venv`) |
| Browser | Chromium aus der vorhandenen Playwright-Installation |
| Datenbank | eigens angelegte, isolierte Datei `backend\var\verify_doku.db`, nach dem Lauf entfernt |
| Provider | ausschliesslich Testprovider; keine externen Aufrufe |

Alle Prüfungen dieses Berichts liefen gegen den oben genannten Commit. Wer
diesen Commit bezieht, erhält denselben Stand von Dokumentation,
Konfigurationsvorlagen, Startskript, Gitignore, Screenshots und der
Secret-Scan-Anpassung.

## 2 Umfang der Änderungen

Produktiver Frontend- und Backend-Code, öffentliche API-Verträge,
Datenbankschemata und Migrationen wurden **nicht** verändert. Angepasst wurden:

- die Produktdokumentation (`docs/SCHNELLSTART.md`,
  `docs/BEDIENUNGSANLEITUNG.md`, `docs/demo/demo-runbook.md`, `README.md`),
- die Konfigurationsvorlagen (`.env.example`, neu `backend/.env.demo.example`),
- die Gitignore-Regeln (Ausnahme für die neue Vorlage),
- das Demo-Startskript `scripts/start_poc_demo.ps1` (zwei gedruckte Hinweistexte),
- die Dateiliste des Secret-Scan-Tests `backend/tests/test_provider_policy.py`,
- die zehn Screenshots unter `docs/assets/bedienungsanleitung/`.

Diese Hilfsdateien sind betriebsrelevant; die Aufzählung nennt sie deshalb
ausdrücklich.

## 3 Umgang mit der lokalen Konfiguration

Auf dem Prüfrechner enthält `backend\.env` reale Provider-Schlüssel und
`AI_EVAL_MODE=real`. Dazu gab es im Verlauf der Arbeit **zwei verschiedene
Vorgehensweisen**, die hier getrennt ausgewiesen werden:

**a) Installationsprüfung des Kopierwegs (früher am 5. August).** Hier wurde der
in der Dokumentation beschriebene Befehl `Copy-Item backend\.env.demo.example
backend\.env` tatsächlich ausgeführt — im bestehenden Arbeitsverzeichnis. Die
vorhandene `backend\.env` wurde vorher ausserhalb des Repositorys gesichert,
vorübergehend durch die Demo-Vorlage ersetzt und nach Abschluss aus der Sicherung
wiederhergestellt. Dasselbe gilt für `.env.local`. Die Prüfung selbst verwendete
ausschliesslich die Demo-Konfiguration.

**b) Abschliessender Prüflauf (dieser Bericht).** Hier wurde **keine**
Konfigurationsdatei verändert. Datenbank, Testprovider und Betriebsart kamen
ausschliesslich aus prozessbezogenen Umgebungsvariablen, die in
pydantic-settings Vorrang vor `.env` haben:

```powershell
$env:DATABASE_URL = "sqlite:///./var/verify_doku.db"
$env:APP_ENV = "development"
$env:DEMO_DATA_ENABLED = "true"
$env:AGENT_FAKE_PROVIDER = "true"
$env:WEB_RESEARCH_ENABLED = "true"
$env:WEB_RESEARCH_FAKE_PROVIDER = "true"
$env:AI_EVAL_MODE = "off"
```

Der in der Dokumentation vorangestellte Schutzblock wurde in Variante b
mitgeprüft: Er löste erwartungsgemäss aus und brach mit der Meldung
«`.env.local` existiert bereits» ab, statt eine bestehende Konfiguration zu
überschreiben.

Bestehende Datenbanken (`backend\app.db`, `backend\var\demo.db`) wurden in
beiden Varianten nicht verändert. Die Prüfdatenbank wurde nach Abschluss
entfernt.

## 4 Ausgeführte Befehle des abschliessenden Prüflaufs

```powershell
# Datenbank (aus backend\, mit den Variablen aus Abschnitt 3b)
.\.venv\Scripts\python.exe -m alembic -c alembic.ini upgrade head
.\.venv\Scripts\python.exe -m app.seed
.\.venv\Scripts\python.exe -m app.demo.seed --reset --evaluation

# Dienste
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
node node_modules/next/dist/bin/next start --port 3000 --hostname 127.0.0.1

# Prüfungen
corepack pnpm exec playwright test golden-path --workers=1 --reporter=list
.\.venv\Scripts\python.exe -m pytest -q tests/test_provider_policy.py
corepack pnpm build
Get-NetTCPConnection -LocalPort 3000,8000 -State Listen
Invoke-WebRequest http://127.0.0.1:8000/api/v1/health
```

Zusätzlich wurden vorab, gegen denselben Produktcode, einzelne Befehle der
Dokumentation geprüft: `corepack pnpm dev` mit und ohne `--hostname 127.0.0.1`
zur Bindungsmessung, `corepack prepare pnpm@11.5.3 --activate` sowie beide
Varianten zur Ausführungsrichtlinie.

## 5 Ergebnisse

| Prüfung | Ergebnis | Nachweis |
|---|---|---|
| Migration auf leerer Datenbank | bestanden — vollständige Alembic-Kette von null | `doku-verifikation-2026-08-05/db-migration.log` |
| Basis-Seed | bestanden | `db-seed.log` |
| Demo-Seed `--reset --evaluation` | bestanden — «demo seed complete» | `db-demo-seed.log` |
| **Golden Path (gezielter E2E-Test)** | **bestanden — 1 Test bestanden, 0 fehlgeschlagen, Exit-Code 0** | `playwright-golden-path.log` |
| Provider-Policy-Test (Secret-Scan über die Vorlagen) | bestanden — 25 Tests, Exit-Code 0 | `pytest-provider-policy.log` |
| Produktions-Build des Frontends | bestanden, Exit-Code 0. Die Build-Ausgabe weist eine TypeScript-Prüfung aus («Running TypeScript … Finished TypeScript»). Eine separate Ausführung von `tsc --noEmit` erfolgte nicht. | `frontend-build.log` |
| Backend-Health | bestanden — `{"status":"ok", …}` | Konsolenausgabe, unten zitiert |
| Bindung Backend | bestanden — `127.0.0.1:8000` | Ausgabe von `Get-NetTCPConnection` |
| Bindung Frontend **mit** `--hostname 127.0.0.1` | bestanden — `127.0.0.1:3000` | Ausgabe von `Get-NetTCPConnection` |
| Schutzblock gegen Überschreiben bestehender `.env` | bestanden — löste aus und brach ab | Abschnitt 3 |
| Screenshots | zehn Aufnahmen erstellt und einzeln gesichtet | `docs/assets/bedienungsanleitung/` |
| Versionsstand | festgehalten | `git-rev.txt`, `git-branch.txt`, `git-status-vor-lauf.txt`, `git-status-nach-lauf.txt` |

Health-Antwort im Wortlaut:
`{"status":"ok","api_version":"1.1.0","policy_version":"1.1.0","agent_registry_version":"1.1.0","rule_registry_version":"1.1.0","tool_registry_version":"1.1.0"}`

Alle Nachweisdateien liegen unter
[`evaluation/doku-verifikation-2026-08-05/`](evaluation/doku-verifikation-2026-08-05/).

### Anmeldung und lokaler Backend-Betrieb

Der Golden-Path-Test meldet sich über die echte Anmeldemaske an, legt ein
Projekt aus Idee und synthetischem PDF an, prüft Importkandidaten, speichert
Partner und Budget, gibt einen öffentlichen Recherchebrief frei, schliesst einen
Analyselauf mit dem Testprovider ab, bearbeitet einen Feldtext, erneuert die
Qualitätsprüfung, öffnet die Innolink-Kopieransicht, kopiert ein Feld, lädt neu
und bestätigt die Persistenz. Sein Bestehen deckt damit den in Teil B der
Anleitung beschriebenen Kernablauf ab.

Die Anwendung lief dabei im **lokalen Backend-Betrieb statt im Browser-Mock**:
Das Frontend arbeitete mit dem lokalen FastAPI-Backend und der persistenten
Testdatenbank. Externe KI- und Recherchedienste waren durch Testprovider
ersetzt; `APP_BACKEND_MODE=live` bedeutet ausschliesslich diese lokale
Backend-Anbindung und **nicht** den Einsatz realer Provider.

## 6 Befunde mit Konsequenz für die Dokumentation

| Befund | Belegt durch | Folge |
|---|---|---|
| **Das Frontend bindet ohne `--hostname` auf alle Netzwerkschnittstellen.** Gemessen: lokale Adresse `::`; Next.js meldete zusätzlich eine erreichbare Netzwerkadresse. Da das Frontend Anfragen an das loopback-gebundene Backend weiterreicht, wäre damit auch die Anwendung samt Demo-Zugangsdaten im lokalen Netz erreichbar. | `Get-NetTCPConnection -LocalPort 3000` vor und nach dem Setzen des Flags | `--hostname 127.0.0.1` ist Teil aller Startbefehle in beiden Dokumenten; Abschnitt 7.2 der Anleitung erklärt den Grund |
| Ein `.next`-Ordner aus einem früheren `corepack pnpm build` lässt den Entwicklungsserver fehlerfrei starten, aber **jede** Route mit `404` antworten. | während der Arbeit beobachtet; nach dem Löschen von `.next` sofort behoben | als Fehlerbild in Abschnitt 19 der Anleitung aufgenommen |
| Bei einer restriktiven PowerShell-Ausführungsrichtlinie werden Skripte aus `scripts\` blockiert («Die Datei … kann nicht geladen werden»). | in einem Kindprozess mit `-ExecutionPolicy Restricted` reproduziert; der Einmal-Aufruf mit `-ExecutionPolicy Bypass` und die prozessbezogene Einstellung wurden beide erfolgreich getestet | Abschnitt 19 empfiehlt den Einmal-Aufruf statt einer dauerhaften Änderung |
| `pnpm` ist im Repository nicht fixiert; verbindlich ist nur `lockfileVersion: '9.0'`. | `package.json`, `pnpm-lock.yaml` | Abschnitt 3 nennt «pnpm ab 9, geprüft mit 11.5.3» und den Ausweichbefehl mit fixer Version |
| `ALLOWED_ORIGINS` ist eine Origin-/CSRF-Prüfung, **keine** CORS-Freigabe; das Backend registriert keine `CORSMiddleware`. | `backend/app/security/deps.py`, `backend/app/security/origin.py` | in Abschnitt 5 der Anleitung korrekt beschrieben |

## 7 Nicht ausgeführt

- **Installation auf einem frisch aufgesetzten Rechner.** Node.js, Python und Git
  waren auf dem Prüfrechner bereits vorhanden. Die Anweisungen zur Installation
  der Systemvoraussetzungen (Abschnitt 3 der Anleitung, Abschnitt 2 des
  Schnellstarts) beruhen auf den offiziellen Bezugsquellen und sind **nicht** in
  einer sauberen Umgebung nachgestellt worden. Das gilt insbesondere für den
  Hinweis zum PATH-Häkchen des Python-Installers.
- **Zeit- und Speichermessungen.** Weder Installationsdauer noch Speicherbedarf
  wurden gemessen; entsprechende Angaben wurden deshalb aus der Dokumentation
  entfernt.
- **Reale Providerpfade.** Es fanden keine Aufrufe an OpenAI, Anthropic, Azure
  OpenAI oder Firecrawl statt. Nicht geprüft sind damit: Erreichbarkeit,
  Modellqualität, Preisregeln, Live-Evaluation und der überwachte
  Live-End-to-End-Ablauf. Der Azure-Zielpfad ist im Backend ohnehin kein
  freigeschalteter Adapter.
- **Innolink-Portal.** Weder die aktuelle Weboberfläche des Portals noch eine
  echte Einreichung wurden geprüft. Die Anwendung schreibt nichts ins Portal.
- **Vollständige Prüfsuiten.** Backend-Gesamtsuite (`pytest` ohne Filter),
  Frontend-Tests (`vitest`), ESLint, `tsc --noEmit`, der **vollständige**
  Playwright-Lauf und `scripts\verify_all.ps1` wurden für diese Überarbeitung
  nicht ausgeführt. Ausgeführt wurden allein der gezielte Golden-Path-Test und
  `tests/test_provider_policy.py`.
- **DOCX-Renderprüfung.** Der Test `backend\tests\test_docx_render_smoke.py`
  benötigt eine lokale Microsoft-Word-Installation und eine interaktive
  Windows-Sitzung; er lief nicht.

## 8 Übersprungen und bekannte Flakes

- **Opt-in-Prüfungen** sind bewusst nicht Teil des Standardgates und liefen nicht:
  `RUN4A_VISUAL`, `RUN4A_REVIEW`, `RUN4B_VISUAL`, `FINAL_ACCEPT` sowie der
  Provider-Erreichbarkeits-Smoke.
- **Bekannter Flake (Stand 23. Juli 2026):** Im Vitest-Gesamtlauf traten zwei
  Zeitüberschreitungen in `test/live-editor-a2.test.tsx` auf; die unmittelbare
  Einzelwiederholung dieser Datei bestand mit 27 Tests. Der Befund wurde in
  dieser Überarbeitung nicht erneut untersucht.
- **Bekannte Einschränkung (Stand 23. Juli 2026):** Ein Lauf der vollständigen
  Backend-Suite erreichte ohne Abschlusszusammenfassung das Zeitlimit und wurde
  deshalb **nicht** als bestanden gewertet.
- **Nicht behobene Beobachtung:** Auf der Exportseite erscheint die
  Feldbezeichnung «Open Editor (…)». Die Projektregeln untersagen diese
  Bezeichnung in der Standardoberfläche. Eine Korrektur wäre eine Änderung am
  Anwendungscode und lag ausserhalb dieses Auftrags; die betroffene
  Bildunterschrift benennt den Zustand nicht als vorbildlich.
- **Nicht behobene Beobachtung:** `final_backend_contracts_v1_1/role_skills_v2.yaml`
  enthält die technische Registry-Kennung `innolink-check-role-skill-contracts`.
  Sie ist nirgends sichtbar, aber der letzte Rest der früheren Produktbezeichnung.

## 9 Screenshots

Zehn Aufnahmen in `docs/assets/bedienungsanleitung/`, erstellt am 5. August 2026
gegen eine isolierte, frisch aufgebaute Datenbank im **Produktionsbetrieb** des
Frontends — dadurch enthält keine Aufnahme den Entwicklungsindikator von
Next.js. Auflösung 1440×900, für Bild 3 wegen der Seitenlänge 1440×1320.

Die Datenbank enthielt ausschliesslich die vier synthetischen Demo-Projekte sowie
ein während der Aufnahme über die Intake-Maske angelegtes synthetisches
Beispielprojekt für die Importprüfung; Reste früherer Golden-Path-Läufe waren
nicht enthalten. Als Vorlage für den Import diente die repo-eigene synthetische
Datei `spike/fixtures/innolink_sample.pdf`; reale Antragsunterlagen aus
`private_inputs/` wurden nicht verwendet.

Jede Aufnahme wurde einzeln auf Namen, E-Mail-Adressen, technische Kennungen,
Zugangsschlüssel und reale Projektdaten gesichtet. Sichtbar ist die synthetische
Demo-Identität «Anna Keller» ohne E-Mail-Adresse; das Benutzermenü zeigt im
geschlossenen Zustand nur Initialen und Anzeigenamen. Eine erste Fassung von
Bild 5 zeigte eine technische Laufkennung im aufgeklappten Bereich «Technische
Details» und wurde deshalb neu aufgenommen. Es wurden keine Maskierungsflächen
verwendet.

Das für die Aufnahme verwendete Playwright-Skript war temporär und wurde nach
dem Lauf entfernt; es ist nicht Teil des Repositorys.

## 10 Aussagegrenze

Bestandene technische Prüfungen belegen einen definierten Softwarestand auf einem
Rechner. Sie sind keine Datenschutz-, Sicherheits-, Fach-, Förder- oder
Produktivfreigabe und sagen nichts über die Förderfähigkeit eines Gesuchs aus.
