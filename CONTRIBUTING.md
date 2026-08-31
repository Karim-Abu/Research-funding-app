# Beitrag leisten

Vielen Dank für Ihr Interesse an diesem Repository. Beiträge sind willkommen, wenn sie nachvollziehbar, getestet und klar dokumentiert sind.

## Grundsätze

- Änderungen klein und fokussiert halten
- Bestehende Architektur und Benennungen respektieren
- Keine Secrets, Zugangsdaten oder personenbezogenen Daten committen
- Nutzerführung und fachliche Nachvollziehbarkeit nicht verschlechtern

## Entwicklungsablauf

1. Problem und Ziel der Änderung kurz beschreiben
2. Relevante Stellen gezielt anpassen
3. Vorhandene Qualitätsprüfungen ausführen
4. Ergebnisse und offene Punkte sauber dokumentieren

## Validierung vor Review

Frontend (Repo-Wurzel):

```bash
corepack pnpm test
corepack pnpm lint
corepack pnpm exec tsc --noEmit
corepack pnpm build
```

Backend (`backend/`):

```bash
.venv/bin/python -m pytest -q
```

Windows entsprechend mit `.venv\\Scripts\\python.exe`.

## Pull-Request-Qualität

Ein guter Pull Request enthält:

- klare Problemstellung
- kurze Begründung der Lösung
- sichtbare Test-/Validierungsergebnisse
- ggf. Hinweise auf bekannte Restpunkte

## Kommunikation

Bitte sachlich, konkret und respektvoll kommunizieren. Ziel ist eine professionelle, transparente Zusammenarbeit.
