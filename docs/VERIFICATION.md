# What was verified, and how

Date: 2026-10-25. Environment: Linux, Python 3.x, git. **No live model session with a real API key was run.** Everything below that involves a real CLI used a **mock API server** (`tests/e2e/mock_anthropic.py`, `mock_openai.py`) that returns canned replies.

## Matrix

| Tool | Level | What was checked | What was *not* checked |
|---|---|---|---|
| **Claude Code 2.1.197** | **Real CLI + mock API** | `Stop`/`SessionEnd` hook fired and the real transcript was captured and pushed; the fake secret in the prompt never reached the remote; `SessionStart` hook output reached the real request body ("SessionStart:startup hook success"); `UserPromptSubmit` injected related teammate work | a real model's use of the context; `PreCompact` against a real CLI; MCP approval flow |
| **Codex 0.164.0** | **Real CLI + mock API** | `init --codex` wrote `notify` and the MCP block; Codex lists the `mcp__ganjineh` tool; `notify` fired and the real rollout file was captured; teammate (Codex) saw the other teammate's (Claude Code) session | real model behavior; the debounce under long sessions |
| **Gemini CLI 0.65.0** | **Real CLI (MCP only)** | `gemini mcp list` shows `ganjineh … Connected` | the chat-file parser (written from docs/guesses, **unverified** against real files); no hook support is used |
| **Cursor** | Config files only | `.cursor/mcp.json` and `.cursor/rules/ganjineh.mdc` are written | never launched Cursor |
| **GitHub Copilot (VS Code)** | Config files only | `.vscode/mcp.json` and `.github/copilot-instructions.md` are written | never launched VS Code |
| **Generic MCP client** | Unit tests | JSON-RPC over stdio via subprocess: initialize, tools/list, each tool call | other clients' quirks |

## Automated tests

- `PYTHONPATH=src pytest tests`: **100 tests** (scrubber, Persian text normalization, search, digest, installer idempotence/uninstall, MCP, two-teammate flows over a local bare repo, concurrent pushes, offline sync, private sessions, Codex notify with a synthetic rollout).
- `tests/e2e/run_e2e.sh`: **9 checks** with the real CLIs above against mock APIs (see `tests/e2e/README.md`). Last run: 9/9 passed.
- Fixtures `tests/fixtures/claude-code-*.jsonl` and `codex-*.jsonl` are real transcripts produced by those CLIs against the mock API.

## Not tested at all

- Any live model session with real keys (quality of recall, whether agents actually use the injected context well).
- Windows and macOS (Linux only).
- A real network git remote such as GitHub (a local bare repo was used for all sync tests).
- Large teams and large brains (performance beyond a few hundred entries).
- Real Gemini chat files, Cursor, Copilot behavior.
- CI: none, because the publishing token lacked the GitHub Actions workflow scope.
