#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
#
# Static checks a reviewer runs against the IMPLEMENTED repository (not this hand-off package).
# Usage:  bash verify/repo_static_checks.sh /path/to/implemented/repo [path/to/built/web/bundle]
#
# These checks are necessary, not sufficient: passing them proves certain forbidden things are absent.
# It proves nothing works. Runtime behaviour is verified with the commands in VERIFICATION.md.
#
# Status of this script itself: written for the hand-off on 2026-11-07 and smoke-tested only on a dummy
# directory tree, because no implementation repository existed. Adjust paths if the repo layout differs
# from the plan (apps/web, services/api, workers/*), and record any change in the verification report.

set -uo pipefail
REPO="${1:?usage: repo_static_checks.sh <repo> [web-bundle-dir]}"
BUNDLE="${2:-$REPO/apps/web/.next}"
fail=0; pass=0
ok()   { echo "PASS  $1"; pass=$((pass+1)); }
bad()  { echo "FAIL  $1"; [ -n "${2:-}" ] && echo "      $2"; fail=$((fail+1)); }
skip() { echo "SKIP  $1 ($2)"; }
grep_src() { grep -RIn --exclude-dir={.git,node_modules,.venv,venv,dist,build,.next,__pycache__} "$@" 2>/dev/null; }

echo "== Licence (D5) =="
if [ -f "$REPO/LICENSE" ] && grep -q "Apache License" "$REPO/LICENSE" && grep -q "Version 2.0" "$REPO/LICENSE"; then ok "LICENSE is Apache-2.0"; else bad "LICENSE missing or not Apache-2.0"; fi
[ -f "$REPO/NOTICE" ] && ok "NOTICE present" || bad "NOTICE missing"
[ -f "$REPO/THIRD_PARTY_NOTICES.md" ] && ok "THIRD_PARTY_NOTICES.md present" || bad "THIRD_PARTY_NOTICES.md missing"
[ -f "$REPO/fixtures/PROVENANCE.md" ] && ok "fixtures/PROVENANCE.md present" || bad "fixtures/PROVENANCE.md missing (D5-06)"
if command -v reuse >/dev/null; then (cd "$REPO" && reuse lint >/dev/null 2>&1) && ok "reuse lint" || bad "reuse lint failed (D5-03)"; else skip "reuse lint" "reuse not installed: pip install reuse"; fi
hits=$(grep_src -l -E '^(unidecode|PyMuPDF|pymupdf|fitz)\b' --include='*.txt' --include='*.toml' --include='*.cfg' --include='*.lock' "$REPO")
[ -z "$hits" ] && ok "no unidecode / PyMuPDF in dependency manifests" || bad "excluded dependency declared" "$hits"

echo "== No mocks in shipped code (REAL-01) =="
hits=$(grep_src -E 'DEMO_MODE' "$REPO" --include='*.py' --include='*.ts' --include='*.tsx' --include='*.yml' --include='*.yaml' --include='.env*' | grep -v -E '/tests?/|/docs?/')
[ -z "$hits" ] && ok "no DEMO_MODE setting in code or config" || bad "DEMO_MODE still referenced" "$hits"
hits=$(grep_src -E 'FakeLLMProvider' "$REPO" --include='*.py' | grep -v -E '/tests?/')
[ -z "$hits" ] && ok "FakeLLMProvider only under tests/" || bad "FakeLLMProvider outside tests/" "$hits"
if [ -d "$BUNDLE" ]; then
  hits=$(grep -RIl -E 'msw|mockServiceWorker|/mocks/' "$BUNDLE" 2>/dev/null | head -5)
  [ -z "$hits" ] && ok "web bundle contains no msw or mocks/ import" || bad "mock code in production bundle" "$hits"
else skip "bundle scan" "no built bundle at $BUNDLE; run the production build first"; fi
hits=$(grep_src -E '"/api/v1/test/|/api/v1/test/' "$REPO" --include='*.py' | grep -v -E '/tests?/')
[ -z "$hits" ] && ok "no /api/v1/test/* routes in application code" || bad "test hook routes present in app code (see errata E1)" "$hits"
hits=$(grep_src -E '^\s*fixture-web:' "$REPO/docker-compose.yml" "$REPO/compose.yaml")
if [ -n "$hits" ]; then
  grep -A6 -E '^\s*fixture-web:' "$REPO"/docker-compose.yml "$REPO"/compose.yaml 2>/dev/null | grep -q 'profiles:.*test' && ok "fixture-web only under profile test" || bad "fixture-web in default stack"
else ok "fixture-web not in default compose services"; fi

echo "== D1: single model gateway =="
hits=$(grep_src -l -E '^\s*(import openai|from openai)' "$REPO" --include='*.py' | grep -v -E '/tests?/|policy_enforced_provider')
[ -z "$hits" ] && ok "only PolicyEnforcedProvider imports openai" || bad "openai imported outside PolicyEnforcedProvider (D1-02)" "$hits"

echo "== Secrets =="
hits=$(grep_src -E 'sk-(proj-)?[A-Za-z0-9_-]{20,}' "$REPO" | grep -v -E 'sk-\.\.\.|sk-x{4,}|sk-<')
[ -z "$hits" ] && ok "no OpenAI-style secret keys in tree" || bad "possible live key committed" "$hits"
if [ -f "$REPO/.env.example" ]; then
  v=$(grep -E '^OPENAI_API_KEY=' "$REPO/.env.example" | cut -d= -f2-)
  [ -z "$v" ] && ok ".env.example leaves OPENAI_API_KEY empty" || bad ".env.example sets OPENAI_API_KEY" "$v"
  grep -qE '^(TAVILY|BRAVE|EXA|SERPAPI)_API_KEY=.+' "$REPO/.env.example" && bad "paid search key prefilled in .env.example" || ok "no paid search key prefilled"
else bad ".env.example missing"; fi

echo "== Wording lints (DD-28, D3-08) =="
hits=$(grep_src -i -E '\b(is|are) (legally )?compliant\b|\bcertified by\b|\bno legal issues\b|\bis sanctioned\b' "$REPO" --include='*.j2' --include='*.jinja' --include='*.md.tmpl' --include='*.tsx' | grep -v -E '/tests?/')
[ -z "$hits" ] && ok "no certification or 'sanctioned' wording in templates/UI copy" || bad "forbidden wording found (check whether it is quoted source text)" "$hits"

echo
echo "static checks: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
