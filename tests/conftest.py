import json, os, subprocess, sys
from pathlib import Path
import pytest

FIX = Path(__file__).parent / "fixtures"
SRC = str(Path(__file__).parent.parent / "src")


def run(args, cwd, env=None, inp=None):
    e = {k: v for k, v in os.environ.items() if not k.startswith(("GANJINEH_", "GONJINEH_")) and k != "CODEX_HOME"}
    e["PYTHONPATH"] = SRC
    e.update(env or {})
    return subprocess.run([sys.executable, "-m", "ganjineh", *args], cwd=cwd, env=e, capture_output=True, text=True, input=inp, timeout=60)


def git(*a, cwd):
    return subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True, check=True).stdout


@pytest.fixture
def team(tmp_path, monkeypatch):
    """A bare brain remote and two teammates, each with their own project clone and GANJINEH_HOME."""
    remote = tmp_path / "brain.git"
    git("init", "-q", "--bare", "-b", "main", str(remote), cwd=tmp_path)
    app = tmp_path / "app-alice"
    app.mkdir()
    git("init", "-q", "-b", "main", cwd=app)
    t = {"remote": remote, "tmp": tmp_path}

    def member(name, area, root):
        env = {"GANJINEH_HOME": str(tmp_path / f"home-{name}"), "HOME": str(tmp_path / f"home-{name}"), "GIT_AUTHOR_NAME": name, "GIT_AUTHOR_EMAIL": f"{name}@x", "GIT_COMMITTER_NAME": name, "GIT_COMMITTER_EMAIL": f"{name}@x"}
        (tmp_path / f"home-{name}").mkdir(exist_ok=True)
        r = run(["init", "--brain", str(remote), "--project", "shop", "--author", name, "--area", area], root, env)
        assert r.returncode == 0, r.stderr + r.stdout
        return env
    t["alice"] = member("alice", "backend", app)
    t["alice_dir"] = app
    git("add", "-A", cwd=app)
    subprocess.run(["git", "-c", "user.name=a", "-c", "user.email=a@a", "commit", "-qm", "init"], cwd=app, check=True)
    bob = tmp_path / "app-bob"
    git("clone", "-q", str(app), str(bob), cwd=tmp_path)
    t["bob"] = member("bob", "frontend", bob)
    t["bob_dir"] = bob
    t["run"] = run
    return t


def claude_lines(prompt, assistant_texts, tool_uses=(), cwd="/proj", sid="sess-1", ts="2026-03-02T10:00:00.000Z"):
    out = [{"type": "user", "message": {"role": "user", "content": prompt}, "cwd": cwd, "sessionId": sid, "timestamp": ts, "gitBranch": "feat/x"}]
    for t in assistant_texts:
        out.append({"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": t}]}, "cwd": cwd, "sessionId": sid, "timestamp": ts})
    for name, inp in tool_uses:
        out.append({"type": "assistant", "message": {"role": "assistant", "content": [{"type": "tool_use", "id": "t1", "name": name, "input": inp}]}, "cwd": cwd, "sessionId": sid, "timestamp": ts})
    return out


def write_jsonl(path, rows):
    Path(path).write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    return path
