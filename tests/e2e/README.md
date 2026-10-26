# End-to-end check with the real CLIs

`run_e2e.sh` installs ganjineh into throwaway projects and drives the **real** Claude Code, Codex and Gemini CLIs
against **mock API servers** that return fixed replies. It checks plumbing: hooks fire, real transcripts parse,
entries reach a bare git remote without the planted secret, MCP connects, and the briefing / related-work text is
present in the request body the CLI sends.

It does **not** prove anything about how a real model behaves. No real API keys are used and none are needed.

## Files

| File | Role |
| --- | --- |
| `run_e2e.sh` | The test. Sets up Alice and Bob, starts the mocks, runs one function per scenario, prints 9 `PASS`/`FAIL` lines. The story is described at the top of the file. |
| `mock_anthropic.py` | Fake Anthropic Messages API (port 18765) for Claude Code. Plays a two-turn "write backend/auth.py" conversation, with a fake API key in the file. Saves the last request body so the test can look for injected hook output. |
| `mock_openai.py` | Fake OpenAI Responses API (port 18766) for Codex. Plays a two-turn "write frontend/LoginForm.tsx" conversation. Logs the tool names Codex offered, so the test can see that ganjineh's MCP server was loaded. |
| `mock_common.py` | HTTP/SSE plumbing both mocks share. |

## Run

```bash
npm i -g @anthropic-ai/claude-code @openai/codex @google/gemini-cli   # or put them on PATH however you like
pkill -f mock_ || true                                                 # stale mocks from an earlier run
E2E_OUT=/tmp/ganjineh-e2e bash tests/e2e/run_e2e.sh
```

A CLI that is not installed is skipped, along with its checks. Everything the run produces (mock request logs,
CLI output, the temporary projects) is in `E2E_OUT`, which is wiped at the start of each run.

Versions used for the recorded run (2026-10-25): Claude Code 2.1.197, Codex 0.164.0, Gemini CLI 0.65.0. Newer CLI
versions may change hook or transcript formats; if a check fails after an upgrade, that is useful information, so
please open an issue with the version.

Note: Codex fires `notify` on every turn, so ganjineh debounces its push by 45 s. The script therefore runs
`ganjineh sync` explicitly before the cross-teammate check.
