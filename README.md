<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/banner-dark.png">
  <img src="assets/banner-light.png" alt="gonjineh (گنجینه): git-native shared memory for a team's AI coding agents. Teammates' sessions (Claude Code, Codex, Gemini) become searchable entries in one git repo." width="100%">
</picture>

**English** · [فارسی](README.fa.md) · [🌐 Live demo](https://mrzroot.github.io/gonjineh/) · [📦 Release v0.1.0](https://github.com/mrzroot/gonjineh/releases/tag/v0.1.0) · [🗒 Changelog](CHANGELOG.md)

![version](https://img.shields.io/badge/version-0.1.0-8e3f4a) ![python](https://img.shields.io/badge/python-3.9%2B-8e3f4a) ![deps](https://img.shields.io/badge/dependencies-none-6f4e37) ![server](https://img.shields.io/badge/server-none-6f4e37) ![llm](https://img.shields.io/badge/LLM%20calls-none-6f4e37) ![tests](https://img.shields.io/badge/tests-99%20passing-6f4e37) ![license](https://img.shields.io/badge/license-MIT-a07a2c)

</div>

> **gonjineh** (گنجینه, "treasury") lets your teammates' AI agents see what your teammate's AI already did. When someone finishes a Claude Code or Codex session, a hook turns the transcript into a small, secret-scrubbed markdown note in a **git repo you own**. Everyone's agents can then search it, and each prompt gets the few most related notes from teammates.

**Contents:** [Why](#-why) · [Install](#-install) · [Quick start](#-quick-start) · [Real output](#-real-output) · [Per-AI setup](#-per-ai-setup) · [How it works](#-how-it-works) · [Privacy](#-privacy-and-the-scrubber) · [Limits & honesty](#-limits--honesty) · [Alternatives](#-alternatives-and-where-this-fits) · [Roadmap](#-roadmap) · [Contributing](#-contributing) · [License](#-license)

## 🎯 Why

You pay for one AI account, or several, and your team uses it on one codebase. One person does the frontend, another the backend. Each person's agent only knows its own chats. So the frontend agent writes a mock for an endpoint that already exists, or proposes JWTs in localStorage after the backend session decided against it.

`gonjineh` makes the chats a **shared, searchable record** without a server or an account:

- **Passive.** Hooks capture finished sessions. Nobody writes notes by hand (you can, with `gonjineh note`).
- **Git is the transport.** One file per session, written only by its author, so pushes never conflict. Your team already has git auth.
- **LLM-free.** The digest is rule-based (asks, outcome, decisions, gotchas, TODOs, files, endpoints, commands). No extra API spend, no data sent to a third party.
- **Scrubbed before it touches disk.** Tokens, keys, card numbers and Iranian mobile numbers are masked first. There is no way to turn the scrubber off for secrets.
- **Persian-aware.** Search normalizes ی/ک variants, ZWNJ and Persian digits, so «ورود» and «login» both work in one corpus.

## 📦 Install

Python 3.9+, standard library only. It is not on PyPI yet:

```bash
pipx install git+https://github.com/mrzroot/gonjineh      # or: pip install git+https://github.com/mrzroot/gonjineh
gonjineh --help
```

## 🚀 Quick start

Create an empty private repo for the team brain (any git host: GitHub, GitLab, a bare repo on a shared box). Then, **once per teammate**, inside each project checkout:

```bash
gonjineh init --brain git@github.com:your-team/team-brain.git --area backend   # --codex also wires Codex (user-level)
git add .gonjineh.json CLAUDE.md AGENTS.md GEMINI.md .github .cursor .mcp.json .gemini .vscode .claude/settings.json
git commit -m "Add gonjineh" && git push
```

Teammates pull that commit and run `gonjineh init --area frontend` (their own area; the brain URL is read from `.gonjineh.json`). That is all: from then on

1. **Session start:** the agent is briefed with recent teammate work.
2. **Each prompt:** if teammates' notes match it, up to 3 are added to the context (never your own notes).
3. **Session end / compaction:** the transcript is digested, scrubbed, committed and pushed in the background.

Everything is also available by hand: `gonjineh search "refund screen"`, `gonjineh who server/routes/auth.py`, `gonjineh recall`, `gonjineh show <id>`, `gonjineh doctor`, `gonjineh uninstall`.

## 🎬 Real output

Produced by [`examples/demo.py`](examples/demo.py) (two teammates, a local bare repo, no network); the full transcript is in [`docs/demo.txt`](docs/demo.txt). Excerpt:

```text
[reza] $ gonjineh search --pull refund screen
[7b88d6deca] 2026-03-02 maryam (claude-code) · backend · Add a refund endpoint for orders. Use POST /api/orders/refund …  (score 3.194)
    files: server/routes/refunds.py, server/models/refund.py
    api:   POST /api/orders/refund
    decision: We decided to store only the last four digits because PCI scope is out of budget.

[reza] $ gonjineh search ورود login
[d737c50590] 2026-03-02 maryam (claude-code) · backend · ایجاد API ورود با ایمیل و رمز: POST /api/login  (score 2.753)
    decision: تصمیم گرفتیم توکن JWT را در کوکی httpOnly بگذاریم چون ذخیره در localStorage امن نیست.

sk_live in git history: False  |  commits: 2      # the fake key in maryam's chat was masked first
```

A stored entry is plain markdown with a small JSON front-matter, so you can read, `grep` and review it in a pull request like any file.

## 🧩 Per-AI setup

What `gonjineh init` writes, and **how far each tool was actually verified** (details in [docs/VERIFICATION.md](docs/VERIFICATION.md)):

| Tool | Capture (write) | Recall (read) | Verified how |
|---|---|---|---|
| **Claude Code** | hooks: `SessionStart`, `UserPromptSubmit`, `Stop`, `SessionEnd`, `PreCompact` in `.claude/settings.json` | briefing + per-prompt injection + MCP | real CLI 2.1.197 against a **mock API**: transcript captured, briefing and teammate notes seen in the request body |
| **Codex** | `notify` hook (user-level `~/.codex/config.toml`, via `init --codex`), rollout read from `~/.codex/sessions` | MCP server + `AGENTS.md` | real CLI 0.164.0 against a **mock API**: notify captured the real rollout, MCP tool listed |
| **Gemini CLI** | `gonjineh capture --format gemini` (no hooks; best-effort parser) | MCP + `GEMINI.md` | real CLI 0.65.0: `mcp list` shows it **Connected**. Chat-file parser **not** verified against real files |
| **Cursor** | `gonjineh note` / MCP `add_note` | `.cursor/mcp.json` + `.cursor/rules` | config files only, **not run** |
| **Copilot (VS Code)** | `gonjineh note` | `.vscode/mcp.json` + `copilot-instructions.md` | config files only, **not run** |
| any other MCP client | `add_note` tool | `search_memory`, `read_entry`, `who_knows_about`, `recent` | MCP protocol tested over stdio in unit tests |

> ⚠️ No live model session with a real API key was run. The real CLIs were driven against mock APIs, which proves the plumbing (hooks fire, files are written, text lands in the request) but not how well a real model uses the context.

## ⚙️ How it works

```
 Claude Code / Codex hook ─▶ parse transcript ─▶ digest (rules) ─▶ scrub ─▶ entries/<project>/<area>/<date>-<author>-<tool>-<id>.md
                                                                                      │ git commit, fetch, rebase, push (retries)
                                                                                      ▼
 prompt ─▶ BM25 over local markdown (+ who-knows) ◀─ git pull ◀──────────────── your team-brain repo
```

- **Digest.** Heuristics pull out what was asked, the outcome, sentences with decision/gotcha markers (English and Persian), TODOs, touched files, API endpoints and commands. Areas (frontend / backend / infra / docs) come from file globs, overridable in `.gonjineh.json`.
- **Storage.** One markdown file per session, only its author writes it, so concurrent pushes cannot conflict. Re-capturing a session overwrites its own file. `INDEX.md` is generated locally and gitignored.
- **Search.** BM25 with field weights, prefix expansion and Persian normalization. No embeddings, no daemon, no database. On a small corpus BM25 scores are tiny, so the per-prompt hook uses a gate: a score threshold *or* at least two distinct query terms found in the entry.
- **Sync.** commit, fetch, `rebase origin/<branch>`, push, up to 4 retries. Offline is fine: entries stay local and go out on the next sync. Codex fires `notify` every turn, so its push is debounced by 45 s.
- **MCP.** `gonjineh mcp` is a stdio JSON-RPC server: `search_memory`, `read_entry`, `add_note`, `who_knows_about`, `recent`.

## 🔒 Privacy and the scrubber

Scrubbing runs on every field **before** anything is written, so secrets never reach git history.

- **Always masked:** AWS, GitHub, GitLab, Slack, Stripe, Anthropic, OpenAI, Google, npm, SendGrid, Twilio, Telegram tokens, JWTs, private-key blocks, `scheme://user:pass@` URLs, `Bearer …`, `password=`/`secret=`-style assignments, long high-entropy blobs, and Luhn-valid card numbers (Latin or Persian digits).
- **PII (on by default, `"pii": false` in `.gonjineh.json` to relax):** Iranian mobile numbers. **Emails are not masked unless you set `"mask_email": true`.**
- **Opt out per session:** write `#private`, `gonjineh:off` or `#نهان` in a prompt and that session is skipped entirely.
- **Opt out per file:** `.brainignore` (gitignore-style) removes matching file paths from entries.
- **Your repo, your access control.** Use a private brain repo. Entries describe your code and decisions, so treat read access like read access to the code.

The scrubber is pattern-based. It will miss secrets with unusual shapes. Do not rely on it as the only control; see [Limits](#-limits--honesty).

## ⚖️ Limits & honesty

- **Heuristic digest, not a summarizer.** It extracts and quotes; it does not understand. Some notes will be noisy or miss the point. Read an entry with `gonjineh show <id>` before trusting it.
- **Search is lexical.** BM25 will not match synonyms that share no words. Persian/English mixed queries work only when the entry contains the term.
- **Scrubbing is best-effort.** It will not catch every secret or personal detail, and anything a teammate types is visible to the whole team.
- **Verification is partial.** See the table above and [docs/VERIFICATION.md](docs/VERIFICATION.md). Not tested: any live model with real keys, Windows, macOS, a real GitHub remote (a local bare repo was used), Cursor and Copilot behavior, Gemini's real chat files.
- **Codex hooks are user-level**, which means `init --codex` edits `~/.codex/config.toml` (inside a marked block; `uninstall --codex` removes it). Claude hooks are project-level and committed.
- **Claude Code and Gemini gates:** project-scoped MCP servers need your approval in Claude Code; Gemini needs a trusted folder.
- **No CI yet.** The token used to publish this repo had no GitHub Actions (workflow) scope, so there is no `.github/workflows`. Run the tests locally: `pip install pytest && PYTHONPATH=src pytest tests`.
- **Young project (v0.1.0).** Expect rough edges and format changes before 1.0.

## 🔍 Alternatives and where this fits

This is a crowded space and several projects are good. **If one of them fits, use it.** A non-exhaustive map from a search on 2026-10-25 (details and caveats in [NOVELTY.md](NOVELTY.md)):

| Project | Shape | Difference to gonjineh |
|---|---|---|
| **gitmem** (dev-boz) | git-synced team memory | the closest; see NOVELTY.md for how the two differ and where it may be better for you |
| **team-memory** (blain3white), **ai-memory** (akitaonrails) | shared memory for agents | different storage/retrieval choices |
| **TeamBrain**, **Krimto**, **Knowit**, **CrewMemory**, **Commonwealth** | team/shared memory, various | several are hosted or use a server or an LLM |
| **claude-mem-sync** | syncs claude-mem across machines | builds on a different local store |
| **iHow Memory**, **mex** | memory / project-context tools | different goal (personal or scaffold context) |

What `gonjineh` bets on: **passive hook capture → LLM-free digest → mandatory scrubber → plain markdown in git → local BM25**, in one stdlib-only Python package with Persian handled as a first-class case. If you want embeddings, a web UI, hosted sync or LLM-written summaries, it deliberately does not do that.

## 🗺️ Roadmap

- Verify with live sessions and a real GitHub remote; publish the results.
- A real Gemini chat-file parser once the format is confirmed, plus Cursor/Copilot capture.
- `gonjineh prune` / retention, and a read-only static HTML export of the brain.
- Optional LLM digest (off by default, bring your own key), only if the scrubber stays in front of it.
- PyPI release and CI, once the publishing token allows workflows.

## 🤝 Contributing

Small, honest PRs are welcome: false-negative secrets for the scrubber, transcript formats for other tools, digest misses. See [CONTRIBUTING.md](CONTRIBUTING.md). Please never paste a real secret into an issue.

## 📄 License

MIT © Mohammadreza Zare. See [LICENSE](LICENSE). If it helps your research or team, [CITATION.cff](CITATION.cff) has a citation.
