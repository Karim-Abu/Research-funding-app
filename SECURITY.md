# Security Policy

## Reporting a Vulnerability

Please do **not** report security issues publicly via Issues or Pull Requests.

Instead, contact the repository owner using the email address listed on the GitHub profile and use:

- Subject: `Security Report: Research-Funding-App`
- Include: affected component, reproduction steps, impact, and suggested mitigation

## Scope

Security-relevant areas include:

- authentication and session handling
- API input validation and authorization boundaries
- secret handling and environment configuration
- file import/export processing
- external provider and web-research integrations

## Security-Related Project Practices

- Fail-closed configuration defaults
- No provider secrets exposed to frontend variables
- Deterministic validation gate for core technical checks
- Data-class-aware controls for provider-backed features

Thank you for responsible disclosure.
