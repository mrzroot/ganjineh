#!/usr/bin/env bash
# Real Claude Code and Codex CLIs against LOCAL MOCK model APIs. No real model, no API key, no network.
# What it proves: hooks fire, transcripts are written in the real formats, gonjineh captures + syncs them,
# and a teammate's brain context shows up in the NEXT request body the real CLI sends.
# What it does NOT prove: anything about how a real model uses that context.
#   usage: tests/e2e/run_e2e.sh      (needs `claude` and `codex` on PATH; skips whichever is missing)
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"; REPO="$(cd "$HERE/../.." && pwd)"
W="${E2E_OUT:-/tmp/gonjineh-e2e}"; rm -rf "$W"; mkdir -p "$W/bin"; export E2E_OUT="$W"
printf '#!/bin/sh\nPYTHONPATH=%s/src exec python3 -m gonjineh "$@"\n' "$REPO" > "$W/bin/gonjineh"; chmod +x "$W/bin/gonjineh"
export PATH="$W/bin:$PATH"
pass=0; fail=0; ok(){ echo "  PASS $1"; pass=$((pass+1)); }; bad(){ echo "  FAIL $1"; fail=$((fail+1)); }
git init -q --bare -b main "$W/brain.git"
export GIT_AUTHOR_NAME=e2e GIT_AUTHOR_EMAIL=e2e@example.com GIT_COMMITTER_NAME=e2e GIT_COMMITTER_EMAIL=e2e@example.com
E2E_PROJ="$W/alice" python3 "$HERE/mock_anthropic.py" & P1=$!
python3 "$HERE/mock_openai.py" & P2=$!
trap 'kill $P1 $P2 2>/dev/null' EXIT; sleep 1

mkdir -p "$W/alice" "$W/homeA" "$W/homeB"
( cd "$W/alice" && git init -q -b main && HOME="$W/homeA" GONJINEH_HOME="$W/homeA/.gj" gonjineh init --brain "$W/brain.git" --project shop --author alice --area backend >/dev/null && git add -A && git commit -qm init )
git clone -q "$W/alice" "$W/bob"

if command -v claude >/dev/null; then
  echo "== Claude Code $(claude --version)"
  ( cd "$W/alice" && HOME="$W/homeA" GONJINEH_HOME="$W/homeA/.gj" ANTHROPIC_BASE_URL=http://127.0.0.1:18765 ANTHROPIC_API_KEY=mock \
      claude -p "build the login endpoint POST /api/login in backend/auth.py" --permission-mode bypassPermissions >"$W/claude.out" 2>&1 )
  sleep 4
  if git --git-dir="$W/brain.git" ls-tree -r --name-only main 2>/dev/null | grep -q 'entries/shop/.*alice-claude-code'; then ok "Stop/SessionEnd hook captured the real transcript and pushed it"; else bad "no alice entry in remote"; fi
  if git --git-dir="$W/brain.git" log -p --all 2>/dev/null | grep -q 'sk-ant-api03-ABCDEFGHIJKLMNOP'; then bad "SECRET LEAKED to remote"; else ok "mock secret in the transcript never reached the remote"; fi
fi

if command -v codex >/dev/null; then
  echo "== $(codex --version)"
  export CODEX_HOME="$W/homeB/.codex"; mkdir -p "$CODEX_HOME"
  cat > "$CODEX_HOME/config.toml" <<TOML
model = "mock-model"
model_provider = "mock"
approval_policy = "never"
sandbox_mode = "workspace-write"
[model_providers.mock]
name = "mock"
base_url = "http://127.0.0.1:18766/v1"
env_key = "MOCK_KEY"
wire_api = "responses"
[projects."$W/bob"]
trust_level = "trusted"
TOML
  ( cd "$W/bob" && HOME="$W/homeB" GONJINEH_HOME="$W/homeB/.gj" gonjineh init --brain "$W/brain.git" --project shop --author bob --area frontend --codex >/dev/null )
  grep -q 'notify = \["gonjineh", "hook", "codex"\]' "$CODEX_HOME/config.toml" && ok "init --codex wrote notify into config.toml" || bad "notify missing"
  ( cd "$W/bob" && HOME="$W/homeB" GONJINEH_HOME="$W/homeB/.gj" MOCK_KEY=x timeout 120 codex exec --skip-git-repo-check "build the login form that calls POST /api/login" >"$W/codex.out" 2>&1 )
  sleep 3
  if grep -q mcp__gonjineh "$W/codex_tools.log"; then ok "real Codex lists the gonjineh MCP server in its tool set"; else bad "gonjineh MCP not in Codex tools"; fi
  # Codex notify fires every turn, so the push is debounced by 45 s; run the sync by hand instead of waiting.
  ( cd "$W/bob" && GONJINEH_HOME="$W/homeB/.gj" gonjineh sync --quiet )
  ( cd "$W/bob" && GONJINEH_HOME="$W/homeB/.gj" gonjineh search --pull login ) | grep -q "bob (codex)" && ok "notify hook captured the real Codex rollout" || bad "no codex entry"
  ( cd "$W/bob" && GONJINEH_HOME="$W/homeB/.gj" gonjineh search login ) | grep -q "alice (claude-code)" && ok "Bob (Codex) sees Alice's (Claude Code) session" || bad "bob does not see alice"
  unset CODEX_HOME
fi

if command -v claude >/dev/null; then
  : > "$W/mock_requests.log"
  ( cd "$W/alice" && HOME="$W/homeA" GONJINEH_HOME="$W/homeA/.gj" ANTHROPIC_BASE_URL=http://127.0.0.1:18765 ANTHROPIC_API_KEY=mock \
      claude -p "add a login form that calls POST /api/login" --permission-mode bypassPermissions >/dev/null 2>&1 )
  if grep -q 'bob \[frontend\]' "$W/lastbody.json" && grep -q 'SessionStart:startup hook success' "$W/lastbody.json"; then ok "SessionStart hook output (with Bob's work) is in the request body the real Claude Code sent"; else bad "briefing not injected"; fi
  if grep -q 'UserPromptSubmit hook success' "$W/lastbody.json" && grep -q 'related work by teammates' "$W/lastbody.json"; then ok "UserPromptSubmit hook injected related teammate work"; else bad "prompt recall not injected"; fi
fi
if command -v gemini >/dev/null; then
  echo "== Gemini CLI $(gemini --version)  (MCP connection only; no model call, no hooks)"
  mkdir -p "$W/homeG"
  ( cd "$W/bob" && HOME="$W/homeG" GEMINI_API_KEY=x GEMINI_CLI_TRUST_WORKSPACE=true GONJINEH_HOME="$W/homeB/.gj" timeout 60 gemini mcp list 2>&1 ) | grep -q "gonjineh.*Connected" && ok "real Gemini CLI connects to the gonjineh MCP server from .gemini/settings.json" || bad "gemini MCP not connected"
fi
echo "passed=$pass failed=$fail"; [ "$fail" = 0 ]
