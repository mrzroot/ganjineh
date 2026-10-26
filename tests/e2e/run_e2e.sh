#!/usr/bin/env bash
# End-to-end check: the REAL Claude Code, Codex and Gemini CLIs against LOCAL MOCK model APIs.
# No real model, no API key, no network.
#
# What it proves:
#   * ganjineh's hooks fire inside the real CLIs and the real transcript formats are parsed;
#   * a session is captured, scrubbed and pushed to a bare git remote (the "brain");
#   * a teammate's work shows up in the NEXT request body the real CLI sends;
#   * Codex and Gemini load ganjineh's MCP server.
# What it does NOT prove: anything about how a real model uses that context.
#
# The story (two teammates, one shared brain repo):
#   1. Alice (Claude Code, backend) builds POST /api/login.            -> her session is pushed to the brain.
#   2. Bob (Codex, frontend) builds the login form against that API.   -> his session is pushed, and he can
#                                                                         search Alice's.
#   3. Alice asks Claude Code for a login form.                        -> Bob's work is injected into the
#                                                                         request body Claude Code sends.
#   4. Gemini CLI only connects to the MCP server (it has no hooks).
#
# usage: tests/e2e/run_e2e.sh      (needs `claude`, `codex`, `gemini` on PATH; a missing one is skipped)
# env:   E2E_OUT  scratch/output directory (default /tmp/ganjineh-e2e; wiped on every run)
set -u

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
WORK="${E2E_OUT:-/tmp/ganjineh-e2e}"

ANTHROPIC_MOCK_URL="http://127.0.0.1:18765"   # keep in sync with PORT in mock_anthropic.py
OPENAI_MOCK_URL="http://127.0.0.1:18766/v1"   # keep in sync with PORT in mock_openai.py

# ---------------------------------------------------------------------------------------------------------------
# Result reporting
# ---------------------------------------------------------------------------------------------------------------
passed=0
failed=0

pass() { echo "  PASS $1"; passed=$((passed + 1)); }
fail() { echo "  FAIL $1"; failed=$((failed + 1)); }

# expect "description" command...   -> PASS if the command succeeds
expect() {
  local description="$1"; shift
  if "$@" >/dev/null 2>&1; then pass "$description"; else fail "$description"; fi
}

# expect_not "description" command... -> PASS if the command fails
expect_not() {
  local description="$1"; shift
  if "$@" >/dev/null 2>&1; then fail "$description"; else pass "$description"; fi
}

# ---------------------------------------------------------------------------------------------------------------
# Who runs what: Alice and Bob each get their own HOME and ganjineh home, like two different machines.
# ---------------------------------------------------------------------------------------------------------------
as_alice() { ( cd "$WORK/alice" && HOME="$WORK/homeA" GANJINEH_HOME="$WORK/homeA/.gj" "$@" ); }
as_bob()   { ( cd "$WORK/bob"   && HOME="$WORK/homeB" GANJINEH_HOME="$WORK/homeB/.gj" "$@" ); }

# Run the real Claude Code as Alice, talking to the Anthropic mock. $1 = prompt, $2 = file for its output.
alice_claude() {
  as_alice env ANTHROPIC_BASE_URL="$ANTHROPIC_MOCK_URL" ANTHROPIC_API_KEY=mock \
    claude -p "$1" --permission-mode bypassPermissions >"$2" 2>&1
}

# The brain remote is a bare repo, so inspect it with plain git (no checkout).
brain_files()   { git --git-dir="$WORK/brain.git" ls-tree -r --name-only main 2>/dev/null; }
brain_history() { git --git-dir="$WORK/brain.git" log -p --all 2>/dev/null; }

# Conditions used by the checks below (each succeeds or fails; they print nothing).
brain_has_entry_from_alice() { brain_files | grep -q 'entries/shop/.*alice-claude-code'; }
brain_ever_contained_secret() { brain_history | grep -q 'sk-ant-api03-ABCDEFGHIJKLMNOP'; }   # prefix of the key planted by mock_anthropic.py
bob_search_finds()           { local needle="$1"; shift; as_bob ganjineh search "$@" | grep -q "$needle"; }
last_request_contains()      { local text; for text in "$@"; do grep -q "$text" "$WORK/lastbody.json" || return 1; done; }   # the Anthropic mock saves the most recent request body here
gemini_lists_ganjineh()      { as_bob env HOME="$WORK/homeG" GEMINI_API_KEY=x GEMINI_CLI_TRUST_WORKSPACE=true timeout 60 gemini mcp list 2>&1 | grep -q 'ganjineh.*Connected'; }

# ---------------------------------------------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------------------------------------------
setup_workdir() {
  rm -rf "$WORK"
  mkdir -p "$WORK/bin" "$WORK/alice" "$WORK/homeA" "$WORK/homeB"
  export E2E_OUT="$WORK"   # the mocks write their recorded requests here

  # `ganjineh` on PATH runs the checkout under test (the hooks call the bare command name).
  printf '#!/bin/sh\nPYTHONPATH=%s/src exec python3 -m ganjineh "$@"\n' "$REPO" > "$WORK/bin/ganjineh"
  chmod +x "$WORK/bin/ganjineh"
  export PATH="$WORK/bin:$PATH"

  # git needs an identity for the commits ganjineh makes in the brain repo.
  export GIT_AUTHOR_NAME=e2e GIT_AUTHOR_EMAIL=e2e@example.com GIT_COMMITTER_NAME=e2e GIT_COMMITTER_EMAIL=e2e@example.com
}

start_mocks() {
  # E2E_PROJ tells the Anthropic mock where Alice's project is (it asks Claude Code to write a file there).
  E2E_PROJ="$WORK/alice" python3 "$HERE/mock_anthropic.py" & ANTHROPIC_PID=$!
  python3 "$HERE/mock_openai.py" & OPENAI_PID=$!
  trap 'kill $ANTHROPIC_PID $OPENAI_PID 2>/dev/null' EXIT
  sleep 1   # give the servers a moment to start listening
}

# A bare brain repo, Alice's project with ganjineh installed, and Bob's clone of that project
# (so Bob gets Alice's committed hook / MCP config, like a teammate pulling the repo).
setup_team() {
  git init -q --bare -b main "$WORK/brain.git"
  ( cd "$WORK/alice" && git init -q -b main \
      && HOME="$WORK/homeA" GANJINEH_HOME="$WORK/homeA/.gj" \
         ganjineh init --brain "$WORK/brain.git" --project shop --author alice --area backend >/dev/null \
      && git add -A && git commit -qm init )
  git clone -q "$WORK/alice" "$WORK/bob"
}

# ---------------------------------------------------------------------------------------------------------------
# 1. Alice, Claude Code: capture and push, secret stays local
# ---------------------------------------------------------------------------------------------------------------
test_claude_capture() {
  echo "== Claude Code $(claude --version)"
  alice_claude "build the login endpoint POST /api/login in backend/auth.py" "$WORK/claude.out"
  sleep 4   # the SessionEnd hook pushes in the background

  expect "Stop/SessionEnd hook captured the real transcript and pushed it" brain_has_entry_from_alice
  # The mock's tool call wrote a fake API key into the transcript; the scrubber must have removed it.
  expect_not "mock secret in the transcript never reached the remote" brain_ever_contained_secret
}

# ---------------------------------------------------------------------------------------------------------------
# 2. Bob, Codex: notify hook, MCP server, and seeing Alice's session
# ---------------------------------------------------------------------------------------------------------------
write_codex_config() {
  # Point Codex at the OpenAI mock and trust Bob's project so it does not prompt.
  cat > "$CODEX_HOME/config.toml" <<TOML
model = "mock-model"
model_provider = "mock"
approval_policy = "never"
sandbox_mode = "workspace-write"
[model_providers.mock]
name = "mock"
base_url = "$OPENAI_MOCK_URL"
env_key = "MOCK_KEY"
wire_api = "responses"
[projects."$WORK/bob"]
trust_level = "trusted"
TOML
}

test_codex_capture_and_search() {
  echo "== $(codex --version)"
  export CODEX_HOME="$WORK/homeB/.codex"
  mkdir -p "$CODEX_HOME"
  write_codex_config

  # --codex also edits ~/.codex/config.toml (here: $CODEX_HOME) to add the `notify` hook and the MCP server.
  as_bob ganjineh init --brain "$WORK/brain.git" --project shop --author bob --area frontend --codex >/dev/null
  expect "init --codex wrote notify into config.toml" \
    grep -q 'notify = \["ganjineh", "hook", "codex"\]' "$CODEX_HOME/config.toml"

  as_bob env MOCK_KEY=x timeout 120 codex exec --skip-git-repo-check \
    "build the login form that calls POST /api/login" >"$WORK/codex.out" 2>&1
  sleep 3

  expect "real Codex lists the ganjineh MCP server in its tool set" grep -q mcp__ganjineh "$WORK/codex_tools.log"

  # Codex fires `notify` after every turn, so ganjineh debounces the push by 45 s. Sync by hand instead of waiting.
  as_bob ganjineh sync --quiet
  expect "notify hook captured the real Codex rollout" bob_search_finds "bob (codex)" --pull login
  expect "Bob (Codex) sees Alice's (Claude Code) session" bob_search_finds "alice (claude-code)" login
  unset CODEX_HOME
}

# ---------------------------------------------------------------------------------------------------------------
# 3. Alice again: Bob's work is injected into the request Claude Code sends
# ---------------------------------------------------------------------------------------------------------------
test_claude_receives_briefing() {
  : > "$WORK/mock_requests.log"
  alice_claude "add a login form that calls POST /api/login" /dev/null

  expect "SessionStart hook output (with Bob's work) is in the request body the real Claude Code sent" \
    last_request_contains 'bob \[frontend\]' 'SessionStart:startup hook success'
  expect "UserPromptSubmit hook injected related teammate work" \
    last_request_contains 'UserPromptSubmit hook success' 'related work by teammates'
}

# ---------------------------------------------------------------------------------------------------------------
# 4. Gemini: MCP connection only
# ---------------------------------------------------------------------------------------------------------------
test_gemini_mcp() {
  echo "== Gemini CLI $(gemini --version)  (MCP connection only; no model call, no hooks)"
  mkdir -p "$WORK/homeG"
  # Bob's clone already has .gemini/settings.json from `ganjineh init`; a fresh HOME keeps Gemini's own state separate.
  expect "real Gemini CLI connects to the ganjineh MCP server from .gemini/settings.json" gemini_lists_ganjineh
}

# ---------------------------------------------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------------------------------------------
setup_workdir
start_mocks
setup_team

command -v claude >/dev/null && test_claude_capture
command -v codex  >/dev/null && test_codex_capture_and_search
command -v claude >/dev/null && test_claude_receives_briefing
command -v gemini >/dev/null && test_gemini_mcp

echo "passed=$passed failed=$failed"
[ "$failed" = 0 ]
