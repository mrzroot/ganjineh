#!/usr/bin/env python3
"""Offline demo: a bare git remote, two teammates, invented sessions. Prints the real output of the real CLI.

    python examples/demo.py
"""
import json, os, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = str(ROOT / "src")
tmp = Path(tempfile.mkdtemp(prefix="ganjineh-demo-"))


def sh(cmd, cwd, env):
    e = {k: v for k, v in os.environ.items() if not k.startswith("GANJINEH_") and k != "CODEX_HOME"}
    e.update(env, PYTHONPATH=SRC)
    return subprocess.run(cmd, cwd=cwd, env=e, capture_output=True, text=True)


def gj(who, *args, show=True):
    r = sh([sys.executable, "-m", "ganjineh", *args], who["dir"], who["env"])
    if show:
        print(f"\n[{who['name']}] $ ganjineh {' '.join(args)}")
        print((r.stdout + r.stderr).rstrip())
    return r


def jsonl(path, rows):
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")


def session(who, sid, prompt, reply, files):
    cwd = str(who["dir"]); ts = "2026-03-02T10:00:00.000Z"
    rows = [{"type": "user", "message": {"role": "user", "content": prompt}, "cwd": cwd, "sessionId": sid, "timestamp": ts, "gitBranch": "main"},
            {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": reply}]}, "cwd": cwd, "sessionId": sid, "timestamp": ts}]
    for f in files:
        rows.append({"type": "assistant", "message": {"role": "assistant", "content": [{"type": "tool_use", "id": "t", "name": "Write", "input": {"file_path": f"{cwd}/{f}"}}]}, "cwd": cwd, "sessionId": sid, "timestamp": ts})
    p = tmp / f"{sid}.jsonl"; jsonl(p, rows); return p


remote = tmp / "team-brain.git"
subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
people = {}
for name, area in (("maryam", "backend"), ("reza", "frontend")):
    d = tmp / f"shop-{name}"; d.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=d, check=True)
    env = {"GANJINEH_HOME": str(tmp / f"home-{name}"), "HOME": str(tmp / f"home-{name}"), "GIT_AUTHOR_NAME": name, "GIT_AUTHOR_EMAIL": f"{name}@example.com", "GIT_COMMITTER_NAME": name, "GIT_COMMITTER_EMAIL": f"{name}@example.com"}
    (tmp / f"home-{name}").mkdir()
    people[name] = {"name": name, "dir": d, "env": env, "area": area}

m, r = people["maryam"], people["reza"]
gj(m, "init", "--brain", str(remote), "--project", "shop", "--author", "maryam", "--area", "backend")
gj(r, "init", "--brain", str(remote), "--project", "shop", "--author", "reza", "--area", "frontend", show=False)

f = session(m, "m1", "Add a refund endpoint for orders. Use POST /api/orders/refund and never store the card number.",
            "Added POST /api/orders/refund in server/routes/refunds.py. We decided to store only the last four digits because PCI scope is out of budget. Gotcha: the refund must be idempotent, so the client sends an Idempotency-Key header. TODO: add the admin screen.",
            ["server/routes/refunds.py", "server/models/refund.py"])
gj(m, "capture", "--file", str(f), "--sync")

f = session(m, "m2", "ایجاد API ورود با ایمیل و رمز: POST /api/login",
            "اندپوینت POST /api/login ساخته شد. تصمیم گرفتیم توکن JWT را در کوکی httpOnly بگذاریم چون ذخیره در localStorage امن نیست. API_KEY=sk_" "live_51Habcdefghijklmnopqrstuv هم در محیط تنظیم شد.",
            ["server/routes/auth.py"])
gj(m, "capture", "--file", str(f), "--sync")

print("\n--- reza's side: he is about to build the refund screen ---")
gj(r, "search", "--pull", "refund", "screen")
gj(r, "who", "server/routes/refunds")
gj(r, "search", "ورود", "login")
gj(r, "recall")
print("\n--- what is actually in the shared git repo (secrets scrubbed before writing) ---")
b = sh(["git", "--git-dir", str(remote), "log", "-p", "--all"], tmp, {}).stdout
print("sk_live in git history:", "sk_live_51H" in b, " |  commits:", sh(["git", "--git-dir", str(remote), "rev-list", "--count", "main"], tmp, {}).stdout.strip())
