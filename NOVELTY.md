# Prior art and what is (and is not) new here

Searches run on **2026-10-25** (web search, README skims; not a code audit). The short version: **team memory for AI coding agents is a crowded, fast-moving area, and gonjineh is not the first.** Several projects below are more mature or more featureful. This file exists so you can pick the right one, and so this repo does not claim more than it should.

## Projects found

| Project | What it is (as far as the README says) | Notes for comparison |
|---|---|---|
| **gitmem** (dev-boz) | Git-synced memory for agents | **The closest.** Same transport idea. Check it first; it may fit you better, particularly if you want what it already offers beyond this project's scope. |
| **team-memory** (blain3white) | Shared memory for a team's agents | Different storage and retrieval choices. |
| **ai-memory** (akitaonrails) | Memory layer for AI agents | Aimed at agents in general, not specifically hook-driven team digests. |
| **TeamBrain** | Shared team knowledge for AI tools | Hosted or server-style in the versions seen. |
| **Krimto**, **Knowit**, **CrewMemory** | Team/shared AI memory products or tools | Various; several rely on a service or on LLM processing. |
| **Commonwealth** | Shared context for agents | Different focus. |
| **claude-mem-sync** | Syncs [claude-mem](https://github.com/thedotmack/claude-mem) data between machines | Builds on claude-mem's own store. |
| **iHow Memory**, **mex** | Memory / project-context tooling | Personal or scaffold-style context rather than team transcript digests. |
| **m-agahi/yadgar** | Project in a similar space | Named in an earlier search; not reviewed in depth, so no claims are made about it. |

Absence from this table means "not found in a quick search", not "does not exist". Descriptions are second-hand summaries and may be out of date; please correct them via an issue.

## The combination gonjineh chooses

None of the individual ideas is new (hooks, git as transport, BM25, scrubbing, MCP). The specific bundle is a bet:

1. **Passive, hook-driven capture** of finished Claude Code and Codex sessions (no manual note-taking), with MCP for the tools that have no hooks.
2. **LLM-free digest.** Rule-based extraction, so no extra API cost and no transcript sent to another provider.
3. **A mandatory scrubber** in front of everything written (secrets, cards, Iranian mobile numbers; email opt-in).
4. **Plain markdown, one file per session, author-only writes, in a git repo you own.** No server, no account, no embeddings, no daemon, no database. Conflict-free by construction.
5. **BM25 search** over those files, with **Persian normalization** (ی/ک, ZWNJ, digits) and per-prompt injection of *teammates'* related work.
6. **Python standard library only**, a single `pipx install`.

## When you should use something else

- You want semantic (embedding) search, a web UI, access control per entry, or hosted sync.
- You want LLM-written summaries of sessions.
- You already use a tool above and it works.
- You need a battle-tested tool today: this is v0.1.0 and verified only partially (see [docs/VERIFICATION.md](docs/VERIFICATION.md)).
