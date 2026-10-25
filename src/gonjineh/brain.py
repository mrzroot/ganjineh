"""Project/user configuration and the git side of the shared brain."""
from __future__ import annotations
import json
import os
import re
import subprocess
import time
from pathlib import Path

PROJECT_FILE = ".gonjineh.json"
BRAIN_IGNORE = ".brainignore"


def home() -> Path:
    return Path(os.environ.get("GONJINEH_HOME") or Path.home() / ".gonjineh")


def git(args, cwd, check=True, timeout=60):
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GIT_ASKPASS="true", LC_ALL="C")
    r = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, timeout=timeout, env=env)
    if check and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {(r.stderr or r.stdout).strip()}")
    return r


def user_config() -> dict:
    p = home() / "config.json"
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return {}


def save_user_config(cfg: dict) -> None:
    home().mkdir(parents=True, exist_ok=True)
    (home() / "config.json").write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n")


def default_author() -> str:
    cfg = user_config()
    if os.environ.get("GONJINEH_AUTHOR"):
        return os.environ["GONJINEH_AUTHOR"]
    if cfg.get("author"):
        return cfg["author"]
    r = subprocess.run(["git", "config", "user.name"], capture_output=True, text=True)
    return (r.stdout.strip() or os.environ.get("USER") or "unknown")


def find_project_root(start: str | Path | None = None) -> Path | None:
    p = Path(start or os.getcwd()).resolve()
    for d in [p, *p.parents]:
        if (d / PROJECT_FILE).exists():
            return d
    return None


def load_project(root: Path) -> dict:
    return json.loads((root / PROJECT_FILE).read_text())


def brain_dir_for(remote: str, project: str) -> Path:
    key = re.sub(r"[^A-Za-z0-9]+", "-", remote or project).strip("-")[-60:] or project
    return home() / "brains" / key


def ensure_brain(path: Path, remote: str | None) -> str:
    """Clone (or init) the brain repo. Returns a status string."""
    path = Path(path)
    if (path / ".git").exists():
        return "exists"
    path.parent.mkdir(parents=True, exist_ok=True)
    if remote:
        r = git(["clone", remote, str(path)], path.parent, check=False, timeout=120)
        if r.returncode == 0:
            if git(["rev-parse", "--verify", "-q", "HEAD"], path, check=False).returncode != 0:
                git(["symbolic-ref", "HEAD", "refs/heads/main"], path)  # empty remote: agree on one branch name
            _seed(path)
            return "cloned"
        # unreachable remote: start local, add remote so a later sync pushes
        path.mkdir(parents=True, exist_ok=True)
        git(["init", "-q", "-b", "main"], path)
        git(["remote", "add", "origin", remote], path)
        _seed(path)
        return "initialised-local (remote unreachable: " + (r.stderr.strip().splitlines() or ["?"])[-1] + ")"
    path.mkdir(parents=True, exist_ok=True)
    git(["init", "-q", "-b", "main"], path)
    _seed(path)
    return "initialised-local"


def _seed(path: Path) -> None:
    gi = path / ".gitignore"
    if not gi.exists():
        gi.write_text("INDEX.md\n.cache/\n")
    rd = path / "README.md"
    if not rd.exists():
        rd.write_text("# Team brain\n\nShared memory for our AI coding agents, managed by [gonjineh](https://github.com/mrzroot/gonjineh).\n"
                      "One markdown file per AI session under `entries/`. Teammates can read these digests; never commit secrets.\n")
    cfg = path / "gonjineh.json"
    if not cfg.exists():
        cfg.write_text(json.dumps({"schema": 1}) + "\n")


def _branch(path: Path) -> str:
    return git(["symbolic-ref", "--short", "HEAD"], path).stdout.strip()


def has_remote(path: Path) -> bool:
    return bool(git(["remote"], path, check=False).stdout.strip())


def commit_local(path: Path, message: str) -> bool:
    paths = [x for x in ("entries", ".gitignore", "README.md", "gonjineh.json") if (path / x).exists()]
    if paths:
        git(["add", "-A", "--", *paths], path)
    if git(["diff", "--cached", "--quiet"], path, check=False).returncode == 0:
        return False
    env_args = ["-c", "user.name=" + (default_author() or "gonjineh"), "-c", "user.email=gonjineh@users.noreply.local"]
    git([*env_args, "commit", "-q", "-m", message], path)
    return True


def sync(path: Path, message: str = "gonjineh: sync", retries: int = 4) -> dict:
    """pull --rebase, commit own entries, push. Entries are one-file-per-session so rebase conflicts cannot happen
    unless two people write the very same file, which the naming scheme prevents."""
    path = Path(path)
    res = {"committed": False, "pulled": False, "pushed": False, "remote": has_remote(path), "error": ""}
    try:
        res["committed"] = commit_local(path, message)
        if not res["remote"]:
            return res
        branch = _branch(path)
        for attempt in range(retries):
            f = git(["fetch", "-q", "origin"], path, check=False)
            if f.returncode != 0:
                res["error"] = "offline: " + f.stderr.strip()[-200:]
                return res
            remote_ref = f"origin/{branch}"
            if git(["rev-parse", "--verify", "-q", remote_ref], path, check=False).returncode == 0:
                r = git(["rebase", remote_ref], path, check=False)
                if r.returncode != 0:
                    git(["rebase", "--abort"], path, check=False)
                    res["error"] = "rebase failed: " + r.stderr.strip()[-200:]
                    return res
                res["pulled"] = True
            p = git(["push", "-q", "-u", "origin", branch], path, check=False)
            if p.returncode == 0:
                res["pushed"] = True
                res["error"] = ""
                return res
            res["error"] = p.stderr.strip()[-200:]
            time.sleep(0.2 * (attempt + 1))
    except RuntimeError as e:
        res["error"] = str(e)
    return res


def pull_only(path: Path, timeout: int = 60) -> bool:
    if not has_remote(path):
        return False
    try:
        if git(["fetch", "-q", "origin"], path, check=False, timeout=timeout).returncode != 0:
            return False
    except subprocess.TimeoutExpired:
        return False
    if git(["rev-parse", "--verify", "-q", "HEAD"], path, check=False).returncode != 0:
        commit_local(path, "gonjineh: seed")  # unborn clone: give rebase something to replay
    branch = _branch(path)
    if git(["rev-parse", "--verify", "-q", f"origin/{branch}"], path, check=False).returncode != 0:
        return False
    return git(["rebase", f"origin/{branch}"], path, check=False).returncode == 0
