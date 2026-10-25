# End-to-end check with the real CLIs

`run_e2e.sh` installs ganjineh into throwaway projects and drives the **real** Claude Code, Codex and Gemini CLIs against **mock API servers** (`mock_anthropic.py` on port 18765, `mock_openai.py` on port 18766) that return fixed replies. It checks plumbing: hooks fire, real transcripts parse, entries reach a bare git remote without the planted secret, MCP connects, and the briefing / related-work text is present in the request body the CLI sends.

It does **not** prove anything about how a real model behaves. No real API keys are used and none are needed.

## Run

```bash
npm i -g @anthropic-ai/claude-code @openai/codex @google/gemini-cli   # or put them on PATH however you like
pkill -f mock_ || true                                                 # stale mocks from an earlier run
E2E_OUT=/tmp/ganjineh-e2e bash tests/e2e/run_e2e.sh
```

Versions used for the recorded run (2026-10-25): Claude Code 2.1.197, Codex 0.164.0, Gemini CLI 0.65.0. Output is 9 `PASS`/`FAIL` lines. Newer CLI versions may change hook or transcript formats; if a check fails after an upgrade, that is useful information, so please open an issue with the version.

Note: Codex fires `notify` on every turn, so ganjineh debounces its push by 45 s. The script therefore runs `ganjineh sync` explicitly before the cross-teammate check.
