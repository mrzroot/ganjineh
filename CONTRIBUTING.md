# Contributing

Thanks for helping. Small PRs with a failing test first are the easiest to review.

```bash
python -m venv .venv && . .venv/bin/activate && pip install pytest
PYTHONPATH=src pytest tests          # 99 tests, a few seconds, no network
```

Rules of the road:

- **Standard library only** at runtime. No new dependencies.
- **Never paste a real secret** in an issue, test or fixture. Use obviously fake values (but shaped like the real thing for scrubber tests).
- **Scrubber changes need tests** both ways: the secret is masked, and ordinary text is not.
- **Be honest in docs.** If you add support for a tool, say how you verified it (real CLI / format fixture / docs only).
- Transcript fixtures should come from a real CLI run against a mock API, with the CLI version in the file name.
- Optional: `tests/e2e/run_e2e.sh` with the real CLIs installed.

Useful contributions: secret shapes the scrubber misses, transcript formats for other tools (Gemini chat files, Cursor, Aider…), digest misses (decisions or gotchas not extracted), Persian text-normalization edge cases, Windows/macOS reports.
