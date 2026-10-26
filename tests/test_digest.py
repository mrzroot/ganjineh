"""Turning a raw session transcript into a compact, scrubbed brain entry (ganjineh.transcripts + ganjineh.digest).

Covers, in order: the recorded real-CLI fixtures (Claude Code, Codex); privacy (secret scrubbing, #private,
ganjineh:off, ignore patterns); what gets extracted (files, endpoints, decisions, TODOs, areas, also in Persian);
robustness (corrupt lines, system reminders, size cap); and the opt-in email masking that goes through the CLI.
"""

import json

from conftest import FIXTURES, claude_lines, run, write_jsonl

from ganjineh import digest, transcripts

CLAUDE_FIXTURE = FIXTURES / "claude-code-2.1.197-mock-api-session.jsonl"
CODEX_FIXTURE = FIXTURES / "codex-0.164.0-mock-api-rollout.jsonl"


def build(rows, tmp_path, **kw):
    """Write fake Claude Code `rows` to a file, parse it, and digest it. Returns (entry, report), or None if skipped."""
    p = write_jsonl(tmp_path / "s.jsonl", rows)
    session = transcripts.read_claude(p)
    return digest.build_entry(session, author="alice", project="shop", **kw)


def test_real_claude_fixture_parses():
    session = transcripts.read_any(CLAUDE_FIXTURE)
    assert session.tool == "claude-code" and session.session_id and session.cwd
    assert [r for r, _ in session.messages][0] == "user"
    assert any(n == "Write" for n, _ in session.tool_calls)


def test_real_claude_fixture_digest():
    session = transcripts.read_any(CLAUDE_FIXTURE)
    entry, report = digest.build_entry(session, author="a", project="p")
    assert entry["files"] == ["backend/auth.py"] and entry["area"] == "backend"
    assert "POST /api/login" in entry["endpoints"]
    assert any("JWT" in d for d in entry["decisions"]) and any("TODO" in t for t in entry["todos"])


def test_real_codex_fixture_digest():
    session = transcripts.read_any(CODEX_FIXTURE)
    assert session.tool == "codex" and session.cwd
    entry, _ = digest.build_entry(session, author="a", project="p")
    assert entry["files"] == ["frontend/LoginForm.tsx"] and entry["area"] == "frontend"
    assert "POST /api/login" in entry["endpoints"]
    # injected AGENTS.md / developer messages must not leak in as user asks
    assert entry["asks"] == ["Build the login form that calls POST /api/login"]


def test_format_autodetect():
    assert transcripts.detect(CLAUDE_FIXTURE) == "claude"
    assert transcripts.detect(CODEX_FIXTURE) == "codex"


def test_secrets_in_prompt_and_reply_are_scrubbed(tmp_path):
    rows = claude_lines(
        "set DB_PASSWORD=hunter2hunter2 and fix login",
        [
            "I used AKIAIOSFODNN7EXAMPLE in the config. We decided to use env vars because the key must not be committed."
        ],
        [("Write", {"file_path": "/proj/backend/cfg.py", "content": "x"})],
    )
    entry, report = build(rows, tmp_path)
    blob = json.dumps(entry)
    assert "hunter2hunter2" not in blob and "AKIAIOSFODNN7EXAMPLE" not in blob
    assert report.total >= 2


def test_private_marker_skips_session(tmp_path):
    rows = claude_lines("#private try something", ["ok"], [("Write", {"file_path": "/proj/a.py"})])
    assert build(rows, tmp_path) is None


def test_ganjineh_off_marker_skips_session(tmp_path):
    assert build(claude_lines("ganjineh:off fix", ["ok"]), tmp_path) is None


def test_brainignore_removes_files_and_skips_when_all_ignored(tmp_path):
    rows = claude_lines(
        "edit", ["done"], [("Edit", {"file_path": "/proj/.env"}), ("Edit", {"file_path": "/proj/src/app.py"})]
    )
    entry, _ = build(rows, tmp_path, ignore_patterns=[".env", "secrets/*"])
    assert entry["files"] == ["src/app.py"]
    rows = claude_lines("edit", ["done"], [("Edit", {"file_path": "/proj/secrets/key.txt"})])
    assert build(rows, tmp_path, ignore_patterns=["secrets/*"]) is None


def test_no_signal_session_skipped(tmp_path):
    assert build(claude_lines("hi", []), tmp_path) is None


def test_area_inference():
    assert digest.infer_areas(["src/components/Button.tsx", "web/app.css"]) == ["frontend"]
    assert digest.infer_areas(["server/routes/users.py"])[0] == "backend"
    assert digest.infer_areas(["Dockerfile"])[0] == "infra"
    assert digest.infer_areas(["weird.xyz"], default="mobile") == ["mobile"]
    assert digest.infer_areas(["a.py", "b.py", "c.tsx"])[0] == "backend"


def test_custom_area_rules():
    rules = [("payments", ["billing/*"]), ("frontend", ["*.tsx"])]
    assert digest.infer_areas(["billing/x.py"], rules) == ["payments"]


def test_endpoints_found_in_code_and_in_reply_text(tmp_path):
    rows = claude_lines(
        "api",
        ["Added GET /api/users/{id} and DELETE /api/users/{id}."],
        [("Write", {"file_path": "/proj/a.py", "content": "@app.post('/api/orders')\nfetch('/api/cart')"})],
    )
    entry, _ = build(rows, tmp_path)
    assert {"GET /api/users/{id}", "DELETE /api/users/{id}", "POST /api/orders"} <= set(entry["endpoints"])
    assert any("/api/cart" in x for x in entry["endpoints"])


def test_persian_session_decisions_and_todos(tmp_path):
    rows = claude_lines(
        "فرم ورود را بساز",
        ["تصمیم گرفتیم از JWT استفاده کنیم چون فرانت SPA است و کوکی مناسب نیست. هنوز refresh token باقی‌مانده است."],
        [("Write", {"file_path": "/proj/web/Login.tsx"})],
    )
    entry, _ = build(rows, tmp_path)
    assert entry["decisions"] and entry["todos"] and entry["area"] == "frontend"


def test_shell_written_files_detected(tmp_path):
    rows = claude_lines("x", ["ok"], [("Bash", {"command": "printf hi > src/new_file.py && echo done 2>&1"})])
    entry, _ = build(rows, tmp_path)
    assert "src/new_file.py" in entry["files"]


def test_codex_apply_patch_files(tmp_path):
    p = tmp_path / "rollout-x.jsonl"
    write_jsonl(
        p,
        [
            {"type": "session_meta", "payload": {"id": "abc", "cwd": "/proj"}},
            {
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "add users endpoint"}],
                },
            },
            {
                "type": "response_item",
                "payload": {
                    "type": "custom_tool_call",
                    "name": "apply_patch",
                    "input": "*** Begin Patch\n*** Update File: server/routes/users.py\n@@\n*** End Patch",
                },
            },
            {
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "Added GET /api/users."}],
                },
            },
        ],
    )
    entry, _ = digest.build_entry(transcripts.read_codex(p), author="a", project="p")
    assert entry["files"] == ["server/routes/users.py"] and "GET /api/users" in entry["endpoints"]


def test_generic_markdown_and_json(tmp_path):
    md = tmp_path / "chat.md"
    md.write_text(
        "User: add dark mode\nAssistant: Done, in src/theme.css. We chose CSS variables instead of a library because it is tiny.\n"
    )
    session = transcripts.read_generic(md)
    assert [r for r, _ in session.messages] == ["user", "assistant"]
    js = tmp_path / "chat.json"
    js.write_text(json.dumps({"messages": [{"role": "user", "content": "hi"}, {"type": "gemini", "content": "yo"}]}))
    assert [r for r, _ in transcripts.read_generic(js).messages][0] == "user"


def test_corrupt_lines_are_skipped(tmp_path):
    p = tmp_path / "s.jsonl"
    p.write_text('not json\n{"type":"user","message":{"role":"user","content":"hello there"},"sessionId":"s"}\n{broken')
    assert transcripts.read_claude(p).messages == [("user", "hello there")]


def test_digest_is_compact_not_a_transcript(tmp_path):
    long = "word " * 5000
    rows = claude_lines(
        long, [long + ". We decided to use X because Y is slow."], [("Write", {"file_path": "/proj/a.py"})]
    )
    entry, _ = build(rows, tmp_path)
    assert len(json.dumps(entry)) < 4000


def test_system_reminders_not_counted_as_prompts(tmp_path):
    rows = [
        {
            "type": "user",
            "message": {"role": "user", "content": "<system-reminder>be nice</system-reminder>"},
            "sessionId": "s",
        }
    ] + claude_lines("real ask", ["ok"], [("Write", {"file_path": "/p/a.py"})])
    entry, _ = build(rows, tmp_path)
    assert entry["asks"] == ["real ask"]


def test_mask_email_is_opt_in_via_config(team):
    """E-mail addresses stay readable by default; `mask_email: true` in the project config hides them."""
    project, env = team["alice_dir"], team["alice"]

    def stored_text_of_note(title):
        found = json.loads(run(["search", "--json", title], project, env).stdout)
        return run(["show", found[0]["id"]], project, env).stdout

    run(["note", "ping dev@example.com about the cart", "--title", "mailone"], project, env)
    assert "dev@example.com" in stored_text_of_note("mailone")

    config_path = project / ".ganjineh.json"
    config = json.loads(config_path.read_text())
    config["mask_email"] = True
    config_path.write_text(json.dumps(config))

    run(["note", "ping other@example.com about orders", "--title", "mailtwo"], project, env)
    assert "other@example.com" not in stored_text_of_note("mailtwo")
