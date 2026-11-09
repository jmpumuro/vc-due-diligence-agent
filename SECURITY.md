# Security

Report security issues privately to the maintainers. Do not open a public issue for vulnerabilities that expose private diligence data, credentials, or tenant isolation failures.

## Scope

- Tenant isolation (`firm_id` / RLS)
- D1 private-document / external AI restrictions
- Auth sessions and demo-session confinement
- Object-store / data-room access controls

## Out of scope (for now)

- Third-party SaaS misconfiguration outside this repository
- Denial-of-service against self-hosted deployments

Please include reproduction steps, affected versions, and whether private document text left the data room boundary.
