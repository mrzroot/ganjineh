"""Entry points called by Claude Code hooks and Codex `notify`. Must never fail loudly or block the agent."""
from __future__ import annotations
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from . import brain, core, store, textnorm, transcripts

MIN_SCORE = 2.5


def spawn_sync(root: str, after: float = 0.0) -> None:
    """Fire-and-forget `ganjineh sync` in a detached process (SessionEnd hooks only get ~1.5 s)."""
    cmd = [sys.executable, "-m", "ganjineh", "sync", "--quiet", "--cwd", str(root)]
    if after:
        cmd += ["--after", str(after)]
    try:
        subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True, close_fds=True)
    except OSError:
        pass


def _find_claude_transcript(data: dict) -> str | None:
    p = data.get("transcript_path")
    if p and Path(p).exists():
        return p
    sid, cwd = data.get("session_id"), data.get("cwd") or os.getcwd()
    if sid:
        cand = transcripts.claude_project_dir(cwd) / f"{sid}.jsonl"
        if cand.exists():
            return str(cand)
    return None


def claude(stdin_text: str, out=sys.stdout) -> int:
    try:
        data = json.loads(stdin_text or "{}")
    except ValueError:
        return 0
    event = data.get("hook_event_name", "")
    cwd = data.get("cwd") or os.getcwd()
    try:
        ctx = core.Ctx.load(cwd)
    except core.NoProject:
        return 0
    except Exception:
        return 0
    try:
        if event == "SessionStart":
            spawn_sync(str(ctx.root))
            try:
                brain.pull_only(ctx.brain, timeout=4)  # fresh teammate work in the very first briefing; never blocks for long
            except Exception:
                pass
            txt = store.briefing(ctx.entries(), ctx.author)
            if txt:
                out.write(txt + "\n")
        elif event == "UserPromptSubmit":
            prompt = data.get("prompt") or ""
            if len(prompt) < 12:
                return 0
            qt = set(textnorm.tokenize(prompt))
            hits = [h for h in store.search(ctx.entries(), prompt, limit=6) if h["author"] != ctx.author
                    and (h["score"] >= MIN_SCORE or len(qt & set(store._fields(h))) >= 2)][:3]
            if hits:
                lines = ["Team brain: related work by teammates (check before you build or assume):"]
                for h in hits:
                    lines.append(f"- [{h['area']}] {h['author']} {h['date']}: {h['title']}" + (f" (files: {', '.join(h.get('files', [])[:3])})" if h.get("files") else "")
                                 + (f" (api: {', '.join(h.get('endpoints', [])[:3])})" if h.get("endpoints") else "") + f" [id {h['id']}]")
                out.write("\n".join(lines)[:1200] + "\n")
        elif event in ("Stop", "SessionEnd", "PreCompact"):
            tp = _find_claude_transcript(data)
            if not tp:
                return 0
            r = core.capture_file(ctx, tp, "claude")
            if r.get("stored"):
                spawn_sync(str(ctx.root), after=0 if event != "Stop" else 45)
    except Exception as e:  # never break the agent
        try:
            (brain.home()).mkdir(parents=True, exist_ok=True)
            with open(brain.home() / "hook-errors.log", "a") as fh:
                fh.write(f"{time.strftime('%F %T')} {event}: {e!r}\n")
        except OSError:
            pass
    return 0


def codex(argv_json: str) -> int:
    try:
        data = json.loads(argv_json or "{}")
    except ValueError:
        return 0
    if data.get("type") not in (None, "agent-turn-complete"):
        return 0
    cwd = data.get("cwd") or os.getcwd()
    try:
        ctx = core.Ctx.load(cwd)
        tid = data.get("thread-id") or data.get("thread_id") or data.get("session_id") or ""
        rollout = transcripts.find_codex_rollout(tid) if tid else None
        if rollout is None:
            return 0
        r = core.capture_file(ctx, rollout, "codex")
        if r.get("stored"):
            spawn_sync(str(ctx.root), after=45)
    except Exception as e:
        try:
            brain.home().mkdir(parents=True, exist_ok=True)
            with open(brain.home() / "hook-errors.log", "a") as fh:
                fh.write(f"{time.strftime('%F %T')} codex: {e!r}\n")
        except OSError:
            pass
    return 0
