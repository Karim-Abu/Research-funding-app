# Security Policy

## Sicherheitsprobleme melden

Bitte melden Sie vermutete Sicherheitslücken **nicht öffentlich** über Issues oder Pull Requests.

Stattdessen:

- Kontakt: über die im GitHub-Profil des Repository-Inhabers hinterlegte E-Mail
- Betreff: `Security Report: Research-Funding-App`
- Inhalt: betroffene Komponente, reproduzierbare Schritte, erwartetes Risiko

Falls Sie keinen direkten Kontakt haben, öffnen Sie ein minimales privates Ticket über die verfügbaren Organisationskanäle.

## Umfang

Relevante Bereiche:

- Authentifizierung und Sitzungsverwaltung
- API-Validierung und Rechteprüfung
- Secret-Handling in Konfiguration und Deployment
- Datei-Import/-Export und externe Integrationen

## Grundprinzipien im Projekt

- Fail-closed Standardkonfigurationen
- Keine Provider-Secrets im Frontend
- Reproduzierbare Validierung mit Tests und Qualitätsgate

Vielen Dank für verantwortungsvolle Offenlegung.
