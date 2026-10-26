"""Shared helpers and fixtures for the test suite.

* `run(...)`   runs the real `ganjineh` CLI in a subprocess (tests exercise the command line, not internals).
* `git(...)`   runs git and returns its output.
* `team`       fixture: a bare "brain" remote plus two teammates (Alice, Bob), each with a project clone and their
               own ganjineh home. Used by the tests that need real git sync between people.
* `claude_lines` / `write_jsonl`   build fake Claude Code transcripts for digest and capture tests.

Fixture files recorded from the real CLIs live in `tests/fixtures/`. The end-to-end run with the real CLIs is in
`tests/e2e/`.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
SRC = str(Path(__file__).parent.parent / "src")

# Variables the CLI reads from the environment; tests must not inherit the developer's own values.
CODEX_HOME_VAR = "CODEX_HOME"
GANJINEH_PREFIX = "GANJINEH_"


def run(args, cwd, env=None, inp=None):
    """Run `python -m ganjineh <args>` in `cwd` and return the CompletedProcess (text output, 60 s timeout).

    The parent environment is passed through, minus ganjineh/Codex variables, so a developer's settings cannot leak
    into a test. Use `env` to add the variables a test needs (e.g. GANJINEH_HOME).
    """
    clean_env = {k: v for k, v in os.environ.items() if not k.startswith(GANJINEH_PREFIX) and k != CODEX_HOME_VAR}
    clean_env["PYTHONPATH"] = SRC
    clean_env.update(env or {})
    return subprocess.run(
        [sys.executable, "-m", "ganjineh", *args],
        cwd=cwd,
        env=clean_env,
        capture_output=True,
        text=True,
        input=inp,
        timeout=60,
    )


def git(*args, cwd):
    """Run git in `cwd`, raise on failure, return stdout."""
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout


def _member_env(tmp_path, name):
    """Environment of one teammate: private HOME / GANJINEH_HOME and a git identity."""
    home = tmp_path / f"home-{name}"
    home.mkdir(exist_ok=True)
    return {
        "GANJINEH_HOME": str(home),
        "HOME": str(home),
        "GIT_AUTHOR_NAME": name,
        "GIT_AUTHOR_EMAIL": f"{name}@x",
        "GIT_COMMITTER_NAME": name,
        "GIT_COMMITTER_EMAIL": f"{name}@x",
    }


def _init_member(remote, project_dir, name, area, tmp_path):
    """`ganjineh init` for one teammate inside their project directory; returns their environment."""
    env = _member_env(tmp_path, name)
    result = run(
        ["init", "--brain", str(remote), "--project", "shop", "--author", name, "--area", area], project_dir, env
    )
    assert result.returncode == 0, result.stderr + result.stdout
    return env


@pytest.fixture
def team(tmp_path):
    """A bare brain remote and two teammates who share one project, like the real setup.

    Alice (backend) creates the project and runs `ganjineh init`; Bob (frontend) clones it and runs `init` too, so he
    receives the config Alice committed. Returned dict keys:

    * `remote`                  path of the bare brain repository
    * `tmp`                     the test's temp directory
    * `alice`, `bob`            environment dicts to pass to `run(..., env=...)`
    * `alice_dir`, `bob_dir`    each teammate's project directory
    """
    remote = tmp_path / "brain.git"
    git("init", "-q", "--bare", "-b", "main", str(remote), cwd=tmp_path)

    alice_dir = tmp_path / "app-alice"
    alice_dir.mkdir()
    git("init", "-q", "-b", "main", cwd=alice_dir)
    alice_env = _init_member(remote, alice_dir, "alice", "backend", tmp_path)
    git("add", "-A", cwd=alice_dir)
    subprocess.run(
        ["git", "-c", "user.name=a", "-c", "user.email=a@a", "commit", "-qm", "init"], cwd=alice_dir, check=True
    )

    bob_dir = tmp_path / "app-bob"
    git("clone", "-q", str(alice_dir), str(bob_dir), cwd=tmp_path)
    bob_env = _init_member(remote, bob_dir, "bob", "frontend", tmp_path)

    return {
        "remote": remote,
        "tmp": tmp_path,
        "alice": alice_env,
        "alice_dir": alice_dir,
        "bob": bob_env,
        "bob_dir": bob_dir,
    }


def claude_lines(prompt, assistant_texts, tool_uses=(), cwd="/proj", sid="sess-1", ts="2026-03-02T10:00:00.000Z"):
    """Rows of a fake Claude Code transcript: one user prompt, then assistant text replies, then tool calls.

    `tool_uses` is a list of `(tool_name, input_dict)`. Every row carries the same cwd, session id and timestamp.
    """

    def assistant_row(content):
        return {
            "type": "assistant",
            "message": {"role": "assistant", "content": content},
            "cwd": cwd,
            "sessionId": sid,
            "timestamp": ts,
        }

    rows = [
        {
            "type": "user",
            "message": {"role": "user", "content": prompt},
            "cwd": cwd,
            "sessionId": sid,
            "timestamp": ts,
            "gitBranch": "feat/x",
        }
    ]
    rows += [assistant_row([{"type": "text", "text": text}]) for text in assistant_texts]
    rows += [
        assistant_row([{"type": "tool_use", "id": "t1", "name": name, "input": tool_input}])
        for name, tool_input in tool_uses
    ]
    return rows


def write_jsonl(path, rows):
    """Write `rows` as one JSON object per line (UTF-8, no ASCII escaping) and return the path."""
    Path(path).write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    return path
