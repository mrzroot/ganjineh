# Changelog

## 0.1.1 (2026-10-26)

- **Renamed to `ganjineh`.** The Persian word گنجینه is pronounced "ganjineh"; 0.1.0 spelled it "gonjineh" by mistake. Repository, package, command, MCP server name, env vars (`GANJINEH_*`), config (`.ganjineh.json`, `~/.ganjineh/`, `.ganjinehignore`) and the instruction-block markers all use the new spelling.
- **Old names keep working.** `gonjineh` is a deprecated alias that prints a one-line notice; `GONJINEH_*` env vars, `.gonjineh.json`, `~/.gonjineh/` and `gonjineh:off` are still read; `.brainignore` is still read. `ganjineh init` migrates old `<!-- gonjineh:begin -->` blocks, hooks, MCP entries, the Cursor rule file and Codex config in place. Hooks written by 0.1.0 (`python3 -m gonjineh ...`) still run through a tiny shim package.
- Plain-language README intro (EN + FA); new 10 compat/migration tests (109 total).
- The old GitHub URL `mrzroot/gonjineh` redirects to `mrzroot/ganjineh`; the old site path `/gonjineh/` redirects to `/ganjineh/`.
- Skip chit-chat sessions (no files touched, no substantive answer) instead of filing them.
- Session briefing no longer calls your own entries a teammate's when you are the only author.

## 0.1.0 (2026-10-25)

First public release.

- Hooks for Claude Code (`SessionStart`, `UserPromptSubmit`, `Stop`, `SessionEnd`, `PreCompact`) and Codex (`notify`).
- Rule-based, LLM-free session digest; one markdown file per session; author-only writes.
- Mandatory secret scrubber plus PII (Iranian mobile numbers), opt-in email masking; `#private` / `ganjineh:off` / `#نهان` and `.brainignore`.
- Git sync (commit, fetch, rebase, push with retries), offline-safe.
- BM25 search with Persian normalization, `who`, `recall`, per-prompt teammate-work injection.
- MCP stdio server (`search_memory`, `read_entry`, `add_note`, `who_knows_about`, `recent`); configs for Claude Code, Cursor, Gemini CLI, VS Code; instruction files for Claude, Codex/AGENTS, Gemini, Copilot, Cursor.
- `init`, `doctor`, `uninstall`. 99 tests; real-CLI e2e against mock APIs (see docs/VERIFICATION.md).
- Known: no CI (publishing token lacked workflow scope); no live-model verification; Gemini chat parser unverified.
