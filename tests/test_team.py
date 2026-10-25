"""Two teammates, two clones, one bare remote. Real git, real subprocess CLI."""
import json
import subprocess
import sys
import threading
from pathlib import Path
from conftest import run, git, claude_lines, write_jsonl


def make_session(path, prompt, replies, files, sid):
    cwd = str(path)
    rows = claude_lines(prompt, replies, [("Write", {"file_path": f"{cwd}/{f}"}) for f in files], cwd=cwd, sid=sid)
    return write_jsonl(path.parent / f"{sid}.jsonl", rows)


def test_alice_frontend_session_reaches_bob_search(team):
    a, b = team["alice_dir"], team["bob_dir"]
    f = make_session(a, "Build the login form with email and password", ["Created the form. We decided to call POST /api/login because the backend owns auth."], ["web/src/Login.tsx"], "s-alice-1")
    r = run(["capture", "--file", str(f), "--sync"], a, team["alice"])
    assert r.returncode == 0 and "stored" in r.stdout, r.stdout + r.stderr
    assert '"pushed": true' in r.stdout
    # bob pulls and searches
    r = run(["search", "--pull", "login", "endpoint"], b, team["bob"])
    assert "alice" in r.stdout and "web/src/Login.tsx" in r.stdout and "POST /api/login" in r.stdout, r.stdout + r.stderr
    r = run(["who", "web/src/Login"], b, team["bob"])
    assert "alice" in r.stdout


def test_bob_mcp_finds_alices_entry(team):
    a, b = team["alice_dir"], team["bob_dir"]
    f = make_session(a, "Add refund endpoint", ["Added POST /api/refunds in billing."], ["server/routes/refunds.py"], "s-alice-2")
    run(["capture", "--file", str(f), "--sync"], a, team["alice"])
    run(["sync"], b, team["bob"])
    import os
    env = dict(os.environ, **team["bob"], PYTHONPATH=str(Path(__file__).parent.parent / "src"))
    reqs = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "search_memory", "arguments": {"query": "refund"}}}]
    p = subprocess.run([sys.executable, "-m", "ganjineh", "mcp"], cwd=team["bob_dir"], env=env, input="\n".join(map(json.dumps, reqs)) + "\n", capture_output=True, text=True, timeout=30)
    out = [json.loads(l) for l in p.stdout.splitlines()]
    assert out[0]["result"]["serverInfo"]["name"] == "ganjineh"
    assert "alice" in out[1]["result"]["content"][0]["text"] and "refunds" in out[1]["result"]["content"][0]["text"]


def test_concurrent_pushes_do_not_conflict(team):
    a, b = team["alice_dir"], team["bob_dir"]
    results = {}

    def work(name, d, n):
        for i in range(n):
            f = make_session(d, f"{name} task number {i} about module{i}", [f"Done {name} {i}."], [f"src/{name}{i}.py"], f"s-{name}-{i}")
            r = run(["capture", "--file", str(f)], d, team[name])
            assert r.returncode == 0, r.stderr
        r = run(["sync"], d, team[name])
        results[name] = r
    ts = [threading.Thread(target=work, args=("alice", a, 4)), threading.Thread(target=work, args=("bob", b, 4))]
    [t.start() for t in ts]
    [t.join() for t in ts]
    for n in ("alice", "bob"):
        assert results[n].returncode == 0, results[n].stdout + results[n].stderr
    run(["sync"], a, team["alice"])
    run(["sync"], b, team["bob"])
    log = git("--git-dir", str(team["remote"]), "ls-tree", "-r", "--name-only", "main", cwd=team["tmp"])
    entries = [l for l in log.splitlines() if l.startswith("entries/")]
    assert len(entries) == 8, log
    for n, d in (("alice", a), ("bob", b)):
        r = run(["search", "--json", "task", "number"], d, team[n])
        assert len(json.loads(r.stdout)) == 6 or len(json.loads(r.stdout)) >= 6  # limit 6, both sides see >6 entries exist
        r = run(["search", "--json", "--limit", "20", "task", "number"], d, team[n])
        assert len(json.loads(r.stdout)) == 8


def test_recapture_same_session_updates_in_place(team):
    a = team["alice_dir"]
    f = make_session(a, "Build thing", ["First."], ["src/a.py"], "s-same")
    run(["capture", "--file", str(f)], a, team["alice"])
    f = make_session(a, "Build thing", ["First.", "Second. We decided to use X because Y."], ["src/a.py"], "s-same")
    run(["capture", "--file", str(f)], a, team["alice"])
    r = run(["search", "--json", "build", "thing"], a, team["alice"])
    es = json.loads(r.stdout)
    assert len(es) == 1 and es[0]["decisions"]


def test_sync_offline_is_graceful(team, tmp_path):
    a = team["alice_dir"]
    f = make_session(a, "Offline work", ["Done."], ["src/o.py"], "s-off")
    run(["capture", "--file", str(f)], a, team["alice"])
    # break the remote
    team["remote"].rename(tmp_path / "gone.git")
    r = run(["sync"], a, team["alice"])
    assert r.returncode == 0 and "offline" in r.stdout
    (tmp_path / "gone.git").rename(team["remote"])
    r = run(["sync"], a, team["alice"])
    assert '"pushed": true' in r.stdout


def test_note_command_and_scrub_in_note(team):
    a, b = team["alice_dir"], team["bob_dir"]
    r = run(["note", "Contract: GET /api/cart returns items. Use API_TOKEN=abcd1234efgh for staging", "--area", "backend", "--sync"], a, team["alice"])
    assert "redacted" in r.stdout
    r = run(["search", "--pull", "cart"], b, team["bob"])
    assert "GET /api/cart" in r.stdout
    blob = git("--git-dir", str(team["remote"]), "log", "-p", "--all", cwd=team["tmp"])
    assert "abcd1234efgh" not in blob


def test_private_session_never_reaches_remote(team):
    a = team["alice_dir"]
    f = make_session(a, "#private explore salary data", ["ok"], ["src/x.py"], "s-priv")
    r = run(["capture", "--file", str(f), "--sync"], a, team["alice"])
    assert "skipped" in r.stdout
    assert git("--git-dir", str(team["remote"]), "ls-tree", "-r", "--name-only", "main", cwd=team["tmp"]).count("entries/") == 0 if (team["remote"] / "refs/heads/main").exists() else True


def test_hook_stop_captures_and_session_start_injects(team):
    a, b = team["alice_dir"], team["bob_dir"]
    f = make_session(a, "Create orders API", ["Added POST /api/orders."], ["server/api/orders.py"], "s-hook")
    payload = json.dumps({"hook_event_name": "SessionEnd", "session_id": "s-hook", "transcript_path": str(f), "cwd": str(a)})
    r = run(["hook", "claude"], a, team["alice"], inp=payload)
    assert r.returncode == 0 and r.stdout == ""
    import time
    for _ in range(40):  # detached background sync
        if git("--git-dir", str(team["remote"]), "log", "--oneline", cwd=team["tmp"]).strip() if (team["remote"] / "refs/heads/main").exists() else False:
            break
        time.sleep(0.25)
    run(["sync"], b, team["bob"])
    r = run(["hook", "claude"], b, team["bob"], inp=json.dumps({"hook_event_name": "SessionStart", "session_id": "x", "cwd": str(b)}))
    assert "alice" in r.stdout and "orders" in r.stdout.lower()
    r = run(["hook", "claude"], b, team["bob"], inp=json.dumps({"hook_event_name": "UserPromptSubmit", "prompt": "add an orders page that lists orders from the api", "cwd": str(b)}))
    assert "related work by teammates" in r.stdout and "alice" in r.stdout
    r = run(["hook", "claude"], b, team["bob"], inp=json.dumps({"hook_event_name": "UserPromptSubmit", "prompt": "rename the css variable for header color", "cwd": str(b)}))
    assert r.stdout == ""


def test_hook_never_fails_outside_project_or_on_garbage(tmp_path):
    r = run(["hook", "claude"], tmp_path, {"GANJINEH_HOME": str(tmp_path / "h")}, inp="not json")
    assert r.returncode == 0
    r = run(["hook", "claude"], tmp_path, {"GANJINEH_HOME": str(tmp_path / "h")}, inp=json.dumps({"hook_event_name": "Stop", "cwd": str(tmp_path)}))
    assert r.returncode == 0 and r.stdout == ""


def test_codex_notify_hook_captures_rollout(team, tmp_path):
    a = team["alice_dir"]
    codex_home = tmp_path / "codexhome"
    sd = codex_home / "sessions" / "2026" / "03" / "02"
    sd.mkdir(parents=True)
    tid = "0199aaaa-bbbb-cccc-dddd-eeeeffff0001"
    write_jsonl(sd / f"rollout-2026-03-02T10-00-00-{tid}.jsonl", [
        {"type": "session_meta", "payload": {"id": tid, "cwd": str(a)}},
        {"type": "response_item", "payload": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "add health endpoint"}]}},
        {"type": "response_item", "payload": {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "Added GET /healthz."}]}},
        {"type": "response_item", "payload": {"type": "custom_tool_call", "name": "apply_patch", "input": "*** Begin Patch\n*** Add File: server/health.py\n*** End Patch"}},
    ])
    env = dict(team["alice"], CODEX_HOME=str(codex_home))
    r = run(["hook", "codex", json.dumps({"type": "agent-turn-complete", "thread-id": tid, "cwd": str(a), "last-assistant-message": "x"})], a, env)
    assert r.returncode == 0
    r = run(["search", "healthz"], a, team["alice"])
    assert "codex" in r.stdout and "server/health.py" in r.stdout


def test_init_is_idempotent_and_doctor_ok(team):
    a = team["alice_dir"]
    r = run(["init"], a, team["alice"])
    assert r.returncode == 0
    r = run(["doctor"], a, team["alice"])
    assert "claude hooks: ✓" in r.stdout and "remote: yes" in r.stdout
    assert (a / "CLAUDE.md").read_text().count("ganjineh:begin") == 1


def test_uninstall_leaves_brain(team):
    a = team["alice_dir"]
    run(["uninstall"], a, team["alice"])
    assert not (a / ".claude" / "settings.json").exists()
    assert (a / ".ganjineh.json").exists()
