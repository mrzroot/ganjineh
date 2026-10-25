"""Readers for agent transcripts. Each returns a normalised Session.

Verified formats: Claude Code (~/.claude/projects/**/*.jsonl) and Codex CLI (~/.codex/sessions/**/rollout-*.jsonl),
see docs/VERIFICATION.md. Others are best-effort and are marked as such there.
"""
from __future__ import annotations
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Session:
    tool: str
    session_id: str
    cwd: str = ""
    branch: str = ""
    started: str = ""
    ended: str = ""
    messages: list = field(default_factory=list)    # (role, text)
    tool_calls: list = field(default_factory=list)  # (name, input dict)
    source: str = ""


def _jsonl(path):
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except ValueError:
                continue


_INJECTED = re.compile(r"^\s*<(environment_context|user_instructions|system-reminder|command-name|command-message|local-command-stdout|ide_|task-notification)|^\s*#\s*AGENTS\.md instructions|^\s*Caveat: The messages below", re.I)


def _text_of(content, kinds=("text", "input_text", "output_text")):
    if isinstance(content, str):
        return content
    out = []
    if isinstance(content, list):
        for b in content:
            if isinstance(b, dict) and b.get("type") in kinds and isinstance(b.get("text"), str):
                out.append(b["text"])
            elif isinstance(b, str):
                out.append(b)
    return "\n".join(out)


def read_claude(path) -> Session:
    s = Session(tool="claude-code", session_id=Path(path).stem, source=str(path))
    for ev in _jsonl(path):
        if not isinstance(ev, dict):
            continue
        ts = ev.get("timestamp") or ""
        if ts:
            s.started = s.started or ts
            s.ended = ts
        s.cwd = s.cwd or ev.get("cwd", "") or ""
        s.branch = s.branch or ev.get("gitBranch", "") or ""
        if ev.get("sessionId"):
            s.session_id = ev["sessionId"]
        if ev.get("isMeta") or ev.get("isSidechain"):
            continue
        t = ev.get("type")
        msg = ev.get("message") or {}
        if t == "user" and isinstance(msg, dict):
            text = _text_of(msg.get("content"))
            if text.strip() and not _INJECTED.search(text):
                s.messages.append(("user", text.strip()))
        elif t == "assistant" and isinstance(msg, dict):
            c = msg.get("content")
            text = _text_of(c)
            if text.strip():
                s.messages.append(("assistant", text.strip()))
            if isinstance(c, list):
                for b in c:
                    if isinstance(b, dict) and b.get("type") == "tool_use":
                        s.tool_calls.append((b.get("name", ""), b.get("input") or {}))
    return s


_PATCH_FILE = re.compile(r"^\*\*\* (?:Update|Add|Delete) File: (.+)$", re.M)


def read_codex(path) -> Session:
    s = Session(tool="codex", session_id=Path(path).stem.replace("rollout-", ""), source=str(path))
    for ev in _jsonl(path):
        if not isinstance(ev, dict):
            continue
        ts = ev.get("timestamp") or ""
        if ts:
            s.started = s.started or ts
            s.ended = ts
        p = ev.get("payload") or {}
        t = ev.get("type")
        if t == "session_meta":
            s.session_id = p.get("id", s.session_id)
            s.cwd = p.get("cwd", s.cwd)
            git = p.get("git") or {}
            s.branch = git.get("branch", s.branch) if isinstance(git, dict) else s.branch
        elif t == "turn_context":
            s.cwd = s.cwd or p.get("cwd", "")
        elif t == "response_item":
            pt = p.get("type")
            if pt == "message":
                text = _text_of(p.get("content"))
                role = p.get("role")
                if role in ("user", "assistant") and text.strip() and not _INJECTED.search(text):
                    s.messages.append((role, text.strip()))
            elif pt == "function_call":
                try:
                    args = json.loads(p.get("arguments") or "{}")
                except ValueError:
                    args = {}
                cmd = args.get("command") if args.get("command") is not None else args.get("cmd")
                if isinstance(cmd, list):
                    cmd = " ".join(map(str, cmd[-1:] if len(cmd) >= 3 and cmd[1] in ("-c", "-lc") else cmd))
                s.tool_calls.append(("Bash", {"command": cmd or ""}))
                if cmd and "apply_patch" in cmd:
                    for f in _PATCH_FILE.findall(cmd):
                        s.tool_calls.append(("Edit", {"file_path": f.strip()}))
            elif pt in ("custom_tool_call", "local_shell_call"):
                inp = p.get("input") or ""
                if isinstance(inp, str):
                    for f in _PATCH_FILE.findall(inp):
                        s.tool_calls.append(("Edit", {"file_path": f.strip()}))
                act = p.get("action") or {}
                if isinstance(act, dict) and act.get("command"):
                    s.tool_calls.append(("Bash", {"command": " ".join(map(str, act["command"]))}))
    return s


def read_generic(path) -> Session:
    """JSON list of {role, content}, JSONL of the same, or markdown with 'User:'/'Assistant:' or '## user' headers."""
    p = Path(path)
    s = Session(tool="chat", session_id=p.stem, source=str(p))
    raw = p.read_text(encoding="utf-8", errors="replace")
    msgs = None
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            data = data.get("messages") or data.get("history") or []
        msgs = data if isinstance(data, list) else None
    except ValueError:
        if p.suffix == ".jsonl":
            msgs = [m for m in _jsonl(p)]
    if msgs is not None:
        for m in msgs:
            if not isinstance(m, dict):
                continue
            role = m.get("role") or {"gemini": "assistant", "model": "assistant", "human": "user"}.get(m.get("type"), m.get("type"))
            role = {"human": "user", "model": "assistant", "gemini": "assistant"}.get(role, role)
            text = _text_of(m.get("content") if "content" in m else m.get("text") or m.get("parts"))
            if role in ("user", "assistant") and text.strip():
                s.messages.append((role, text.strip()))
        return s
    cur, buf = None, []
    hdr = re.compile(r"^(?:#{1,4}\s*)?(user|human|you|assistant|ai|claude|gpt|codex|gemini)\s*[:：]?\s*$|^(user|human|assistant|ai)\s*:\s*(.*)$", re.I)
    for line in raw.splitlines():
        m = hdr.match(line.strip())
        if m:
            if cur and "".join(buf).strip():
                s.messages.append((cur, "\n".join(buf).strip()))
            name = (m.group(1) or m.group(2)).lower()
            cur = "user" if name in ("user", "human", "you") else "assistant"
            buf = [m.group(3)] if m.group(3) else []
        else:
            buf.append(line)
    if cur and "".join(buf).strip():
        s.messages.append((cur, "\n".join(buf).strip()))
    return s


def detect(path) -> str:
    p = Path(path)
    parts = str(p)
    if "/.claude/" in parts or "\\.claude\\" in parts:
        return "claude"
    if "/.codex/" in parts or p.name.startswith("rollout-"):
        return "codex"
    try:
        with open(p, "r", encoding="utf-8", errors="replace") as fh:
            for _ in range(5):
                line = fh.readline()
                if not line:
                    break
                try:
                    ev = json.loads(line)
                except ValueError:
                    continue
                if isinstance(ev, dict):
                    if ev.get("type") in ("session_meta", "response_item", "event_msg", "turn_context"):
                        return "codex"
                    if ev.get("type") in ("user", "assistant", "summary", "system", "file-history-snapshot") or "sessionId" in ev:
                        return "claude"
    except OSError:
        pass
    return "generic"


def read_any(path, fmt="auto") -> Session:
    fmt = detect(path) if fmt == "auto" else fmt
    return {"claude": read_claude, "codex": read_codex}.get(fmt, read_generic)(path)


def claude_project_dir(cwd: str, home: str | None = None) -> Path:
    home = home or os.path.expanduser("~")
    enc = re.sub(r"[^A-Za-z0-9]", "-", cwd)
    return Path(home) / ".claude" / "projects" / enc


def find_codex_rollout(thread_id: str, home: str | None = None):
    base = Path(os.environ.get("CODEX_HOME") or Path(home or os.path.expanduser("~")) / ".codex") / "sessions"
    if not base.exists():
        return None
    hits = sorted(base.rglob(f"rollout-*{thread_id}*.jsonl"))
    return hits[-1] if hits else None
