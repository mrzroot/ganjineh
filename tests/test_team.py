"""Teamwork through the real CLI: two teammates, two clones, one bare "brain" remote, real git and subprocesses.

Alice (backend) and Bob (frontend) come from the `team` fixture in conftest.py. The tests follow the product flow:
capture a session -> sync through the remote -> the other person finds it (search, `who`, MCP, hooks). Then the
safety nets: concurrent pushes, re-capture, offline remote, secrets and `#private` never leaving the machine, and
`init` / `doctor` / `uninstall`.
"""

import json
import os
import subprocess
import sys
import threading
import time

from conftest import SRC, claude_lines, git, run, write_jsonl

from ganjineh import brain

DEFAULT_SEARCH_LIMIT = 6  # `ganjineh search` returns at most this many hits unless --limit is given


# --- helpers ---------------------------------------------------------------------------------------------------


def make_session(project_dir, prompt, replies, files, session_id):
    """Write a fake Claude Code transcript (next to the project dir) in which `files` were written; return its path."""
    cwd = str(project_dir)
    tool_calls = [("Write", {"file_path": f"{cwd}/{name}"}) for name in files]
    rows = claude_lines(prompt, replies, tool_calls, cwd=cwd, sid=session_id)
    return write_jsonl(project_dir.parent / f"{session_id}.jsonl", rows)


def remote_has_commits(team):
    """True once something has been pushed to the brain remote (an empty bare repo has no main branch yet)."""
    return (team["remote"] / "refs/heads/main").exists()


def remote_files(team):
    """Paths stored on the remote's main branch (empty list while nothing is pushed)."""
    if not remote_has_commits(team):
        return []
    out = git("--git-dir", str(team["remote"]), "ls-tree", "-r", "--name-only", "main", cwd=team["tmp"])
    return out.splitlines()


def remote_history(team):
    """Every patch ever pushed to the remote, as text; lets a test prove a secret never appeared in it."""
    return git("--git-dir", str(team["remote"]), "log", "-p", "--all", cwd=team["tmp"])


def wait_for_push(team, attempts=40, delay=0.25):
    """Wait for a hook's detached background sync to push (the hook command itself returns immediately)."""
    for _ in range(attempts):
        if remote_has_commits(team):
            return
        time.sleep(delay)


def hook_claude(project_dir, env, event):
    """Send a Claude Code hook event (a dict, as JSON on stdin) to `ganjineh hook claude`."""
    return run(["hook", "claude"], project_dir, env, inp=json.dumps(event))


# --- the main flow: Alice's work reaches Bob -------------------------------------------------------------------


def test_alice_frontend_session_reaches_bob_search(team):
    alice_dir, bob_dir = team["alice_dir"], team["bob_dir"]
    session = make_session(
        alice_dir,
        "Build the login form with email and password",
        ["Created the form. We decided to call POST /api/login because the backend owns auth."],
        ["web/src/Login.tsx"],
        "s-alice-1",
    )

    captured = run(["capture", "--file", str(session), "--sync"], alice_dir, team["alice"])
    assert captured.returncode == 0 and "stored" in captured.stdout, captured.stdout + captured.stderr
    assert '"pushed": true' in captured.stdout

    found = run(["search", "--pull", "login", "endpoint"], bob_dir, team["bob"])
    output = found.stdout + found.stderr
    assert "alice" in found.stdout and "web/src/Login.tsx" in found.stdout and "POST /api/login" in found.stdout, output

    assert "alice" in run(["who", "web/src/Login"], bob_dir, team["bob"]).stdout


def test_bob_mcp_finds_alices_entry(team):
    alice_dir, bob_dir = team["alice_dir"], team["bob_dir"]
    session = make_session(
        alice_dir,
        "Add refund endpoint",
        ["Added POST /api/refunds in billing."],
        ["server/routes/refunds.py"],
        "s-alice-2",
    )
    run(["capture", "--file", str(session), "--sync"], alice_dir, team["alice"])
    run(["sync"], bob_dir, team["bob"])

    # Speak MCP (JSON-RPC lines on stdin) to the real `ganjineh mcp` server, as an MCP client would.
    requests = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "t", "version": "0"},
            },
        },
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "search_memory", "arguments": {"query": "refund"}},
        },
    ]
    env = dict(os.environ, **team["bob"], PYTHONPATH=SRC)
    server = subprocess.run(
        [sys.executable, "-m", "ganjineh", "mcp"],
        cwd=bob_dir,
        env=env,
        input="\n".join(json.dumps(r) for r in requests) + "\n",
        capture_output=True,
        text=True,
        timeout=30,
    )

    replies = [json.loads(line) for line in server.stdout.splitlines()]
    assert replies[0]["result"]["serverInfo"]["name"] == "ganjineh"
    tool_text = replies[1]["result"]["content"][0]["text"]
    assert "alice" in tool_text and "refunds" in tool_text


def test_hook_stop_captures_and_session_start_injects(team):
    alice_dir, bob_dir = team["alice_dir"], team["bob_dir"]
    session = make_session(
        alice_dir, "Create orders API", ["Added POST /api/orders."], ["server/api/orders.py"], "s-hook"
    )

    # Alice's session ends: the hook captures it and returns at once (stdout must stay empty for Claude Code).
    ended = hook_claude(
        alice_dir,
        team["alice"],
        {
            "hook_event_name": "SessionEnd",
            "session_id": "s-hook",
            "transcript_path": str(session),
            "cwd": str(alice_dir),
        },
    )
    assert ended.returncode == 0 and ended.stdout == ""
    wait_for_push(team)
    run(["sync"], bob_dir, team["bob"])

    # Bob starts a session: the briefing contains Alice's work.
    started = hook_claude(
        bob_dir, team["bob"], {"hook_event_name": "SessionStart", "session_id": "x", "cwd": str(bob_dir)}
    )
    assert "alice" in started.stdout and "orders" in started.stdout.lower()

    # Bob's related prompt gets teammate work injected; an unrelated prompt gets nothing.
    related = hook_claude(
        bob_dir,
        team["bob"],
        {
            "hook_event_name": "UserPromptSubmit",
            "prompt": "add an orders page that lists orders from the api",
            "cwd": str(bob_dir),
        },
    )
    assert "related work by teammates" in related.stdout and "alice" in related.stdout

    unrelated = hook_claude(
        bob_dir,
        team["bob"],
        {
            "hook_event_name": "UserPromptSubmit",
            "prompt": "rename the css variable for header color",
            "cwd": str(bob_dir),
        },
    )
    assert unrelated.stdout == ""


def test_codex_notify_hook_captures_rollout(team, tmp_path):
    alice_dir = team["alice_dir"]
    codex_home = tmp_path / "codexhome"
    sessions_dir = codex_home / "sessions" / "2026" / "03" / "02"
    sessions_dir.mkdir(parents=True)
    thread_id = "0199aaaa-bbbb-cccc-dddd-eeeeffff0001"
    # A minimal Codex rollout file: metadata, one user message, one reply, one apply_patch call.
    write_jsonl(
        sessions_dir / f"rollout-2026-03-02T10-00-00-{thread_id}.jsonl",
        [
            {"type": "session_meta", "payload": {"id": thread_id, "cwd": str(alice_dir)}},
            {
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "add health endpoint"}],
                },
            },
            {
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "Added GET /healthz."}],
                },
            },
            {
                "type": "response_item",
                "payload": {
                    "type": "custom_tool_call",
                    "name": "apply_patch",
                    "input": "*** Begin Patch\n*** Add File: server/health.py\n*** End Patch",
                },
            },
        ],
    )

    # Codex runs `notify` with the event as a JSON command-line argument after each turn.
    notify_event = {
        "type": "agent-turn-complete",
        "thread-id": thread_id,
        "cwd": str(alice_dir),
        "last-assistant-message": "x",
    }
    env = dict(team["alice"], CODEX_HOME=str(codex_home))
    assert run(["hook", "codex", json.dumps(notify_event)], alice_dir, env).returncode == 0

    found = run(["search", "healthz"], alice_dir, team["alice"])
    assert "codex" in found.stdout and "server/health.py" in found.stdout


def test_note_command_and_scrub_in_note(team):
    alice_dir, bob_dir = team["alice_dir"], team["bob_dir"]
    note = "Contract: GET /api/cart returns items. Use API_TOKEN=abcd1234efgh for staging"

    added = run(["note", note, "--area", "backend", "--sync"], alice_dir, team["alice"])
    assert "redacted" in added.stdout

    assert "GET /api/cart" in run(["search", "--pull", "cart"], bob_dir, team["bob"]).stdout
    assert "abcd1234efgh" not in remote_history(team)


# --- safety nets ---------------------------------------------------------------------------------------------


def test_concurrent_pushes_do_not_conflict(team):
    """Both teammates capture four sessions at the same time; nothing may be lost or fail to push."""
    sessions_each = 4
    sync_results = {}

    def work(name):
        project_dir = team[f"{name}_dir"]
        for i in range(sessions_each):
            session = make_session(
                project_dir,
                f"{name} task number {i} about module{i}",
                [f"Done {name} {i}."],
                [f"src/{name}{i}.py"],
                f"s-{name}-{i}",
            )
            captured = run(["capture", "--file", str(session)], project_dir, team[name])
            assert captured.returncode == 0, captured.stderr
        sync_results[name] = run(["sync"], project_dir, team[name])

    threads = [threading.Thread(target=work, args=(name,)) for name in ("alice", "bob")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    for name in ("alice", "bob"):
        result = sync_results[name]
        assert result.returncode == 0, result.stdout + result.stderr
    run(["sync"], team["alice_dir"], team["alice"])
    run(["sync"], team["bob_dir"], team["bob"])

    stored = [path for path in remote_files(team) if path.startswith("entries/")]
    assert len(stored) == 2 * sessions_each, stored

    for name in ("alice", "bob"):
        project_dir = team[f"{name}_dir"]
        capped = json.loads(run(["search", "--json", "task", "number"], project_dir, team[name]).stdout)
        assert len(capped) == DEFAULT_SEARCH_LIMIT  # 8 entries exist, the default limit shows 6
        everything = json.loads(
            run(["search", "--json", "--limit", "20", "task", "number"], project_dir, team[name]).stdout
        )
        assert len(everything) == 2 * sessions_each


def test_recapture_same_session_updates_in_place(team):
    alice_dir = team["alice_dir"]
    first = make_session(alice_dir, "Build thing", ["First."], ["src/a.py"], "s-same")
    run(["capture", "--file", str(first)], alice_dir, team["alice"])
    # The same session grew by one reply, so capturing again must update the entry, not add a second one.
    longer = make_session(
        alice_dir, "Build thing", ["First.", "Second. We decided to use X because Y."], ["src/a.py"], "s-same"
    )
    run(["capture", "--file", str(longer)], alice_dir, team["alice"])

    entries = json.loads(run(["search", "--json", "build", "thing"], alice_dir, team["alice"]).stdout)
    assert len(entries) == 1 and entries[0]["decisions"]


def test_sync_offline_is_graceful(team, tmp_path):
    alice_dir = team["alice_dir"]
    session = make_session(alice_dir, "Offline work", ["Done."], ["src/o.py"], "s-off")
    run(["capture", "--file", str(session)], alice_dir, team["alice"])

    moved_away = tmp_path / "gone.git"
    team["remote"].rename(moved_away)  # the remote becomes unreachable
    offline = run(["sync"], alice_dir, team["alice"])
    assert offline.returncode == 0 and "offline" in offline.stdout

    moved_away.rename(team["remote"])  # ... and comes back: the queued work is pushed
    assert '"pushed": true' in run(["sync"], alice_dir, team["alice"]).stdout


def test_private_session_never_reaches_remote(team):
    alice_dir = team["alice_dir"]
    session = make_session(alice_dir, "#private explore salary data", ["ok"], ["src/x.py"], "s-priv")

    captured = run(["capture", "--file", str(session), "--sync"], alice_dir, team["alice"])
    assert "skipped" in captured.stdout
    assert [path for path in remote_files(team) if path.startswith("entries/")] == []


def test_hook_never_fails_outside_project_or_on_garbage(tmp_path):
    """A hook must never break the user's AI tool: exit 0 and print nothing, whatever it is given."""
    env = {"GANJINEH_HOME": str(tmp_path / "h")}

    garbage = run(["hook", "claude"], tmp_path, env, inp="not json")
    assert garbage.returncode == 0

    outside_project = hook_claude(tmp_path, env, {"hook_event_name": "Stop", "cwd": str(tmp_path)})
    assert outside_project.returncode == 0 and outside_project.stdout == ""


# --- install / uninstall -------------------------------------------------------------------------------------


def test_init_is_idempotent_and_doctor_ok(team):
    alice_dir = team["alice_dir"]
    assert run(["init"], alice_dir, team["alice"]).returncode == 0

    doctor = run(["doctor"], alice_dir, team["alice"])
    assert "claude hooks: ✓" in doctor.stdout and "remote: yes" in doctor.stdout
    assert (alice_dir / "CLAUDE.md").read_text().count("ganjineh:begin") == 1


def test_uninstall_leaves_brain(team):
    alice_dir = team["alice_dir"]
    run(["uninstall"], alice_dir, team["alice"])
    assert not (alice_dir / ".claude" / "settings.json").exists()
    assert (alice_dir / ".ganjineh.json").exists()


def test_ignore_files_are_the_two_known_names():
    assert brain.IGNORE_FILES == (".ganjinehignore", ".brainignore")
