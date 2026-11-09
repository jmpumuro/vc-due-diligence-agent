# Verification

Quick checks before treating a build as release-ready. Someone other than the implementer should rerun the release-blocking commands (Gate H).

## Must pass (no OpenAI key required)

```bash
cp -n .env.example .env
docker compose up --build -d
curl -fsS http://localhost:3000/ >/dev/null
curl -fsS http://localhost:8001/health/live
uv sync --all-packages
uv run pytest -q
uv run python scripts/licence_gate.py
```

## Automatic fails

| # | Condition |
| --- | --- |
| F1 | UI does not load without an OpenAI key |
| F2 | Demo / MSW / fake network stubs in shipped paths |
| F3 | Live secrets committed to the repo or browser bundle |
| F4 | Licence gate fails or project is not Apache-2.0 |
| F5 | Private-document text leaves the data room without D1 authorization |
| F6 | Report numbers that do not trace to stored evidence |

## Living references

- Remediation gates: `docs/remediation-backlog.md`
- Domain model: `docs/domain-specification.md`
- Architecture decisions: `docs/adr/`
- Contracts in code: `packages/contracts`
