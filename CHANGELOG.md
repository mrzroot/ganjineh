# Changelog

## Unreleased

- Skip chit-chat sessions (no files touched, no substantive answer) instead of filing them.
- Session briefing no longer calls your own entries a teammate's when you are the only author.

## 0.1.0 (2026-10-25)

First public release.

- Hooks for Claude Code (`SessionStart`, `UserPromptSubmit`, `Stop`, `SessionEnd`, `PreCompact`) and Codex (`notify`).
- Rule-based, LLM-free session digest; one markdown file per session; author-only writes.
- Mandatory secret scrubber plus PII (Iranian mobile numbers), opt-in email masking; `#private` / `gonjineh:off` / `#نهان` and `.brainignore`.
- Git sync (commit, fetch, rebase, push with retries), offline-safe.
- BM25 search with Persian normalization, `who`, `recall`, per-prompt teammate-work injection.
- MCP stdio server (`search_memory`, `read_entry`, `add_note`, `who_knows_about`, `recent`); configs for Claude Code, Cursor, Gemini CLI, VS Code; instruction files for Claude, Codex/AGENTS, Gemini, Copilot, Cursor.
- `init`, `doctor`, `uninstall`. 99 tests; real-CLI e2e against mock APIs (see docs/VERIFICATION.md).
- Known: no CI (publishing token lacked workflow scope); no live-model verification; Gemini chat parser unverified.
