"""Writes the managed instruction blocks, hooks and MCP config. Idempotent; `uninstall` removes only what we added."""
from __future__ import annotations
import json
import os
import re
import shutil
from pathlib import Path

BEGIN, END = "<!-- ganjineh:begin -->", "<!-- ganjineh:end -->"
BLOCK = f"""{BEGIN}
## Team brain (ganjineh)

This project shares AI-session memory between teammates (frontend, backend, ...). Another person's AI may already have built, decided or documented what you are about to touch.

1. **Before** you assume a feature, endpoint, component or model is missing, or decide how to build something: call the MCP tool `search_memory` (or run `ganjineh search "<words>"`). Use `who_knows_about` for a file or endpoint.
2. **After** you make a decision, define an API contract or hit a gotcha that a teammate's AI would need, call `add_note` (short, factual, no secrets).
3. Never write secrets, tokens or personal data into notes. A session whose first prompt contains `#private` is never captured.
4. Memory can be stale: verify against the code before relying on it.
{END}
"""
# Pre-0.1.1 names (the project was briefly spelled "gonjineh"); recognised and migrated by `init`, never written.
LEGACY_BEGIN, LEGACY_END = "<!-- gonjineh:begin -->", "<!-- gonjineh:end -->"
LEGACY_MDC = ".cursor/rules/gonjineh.mdc"
LEGACY_HOOK_MARK = "gonjineh hook"
LEGACY_CODEX_BEGIN, LEGACY_CODEX_END = "# >>> gonjineh (managed) >>>", "# <<< gonjineh (managed) <<<"
MDC_HEAD = "---\ndescription: Shared team memory (ganjineh): search it before assuming what exists in another part of the codebase\nalwaysApply: true\n---\n"
INSTRUCTION_FILES = ["CLAUDE.md", "AGENTS.md", "GEMINI.md", ".github/copilot-instructions.md", ".cursor/rules/ganjineh.mdc"]
HOOK_MARK = "ganjineh hook"
HOOK_MARKS = (HOOK_MARK, LEGACY_HOOK_MARK)
CLAUDE_EVENTS = ["SessionStart", "UserPromptSubmit", "Stop", "SessionEnd", "PreCompact"]


def exe() -> str:
    return "ganjineh" if shutil.which("ganjineh") else "python3 -m ganjineh"


def write_block(path: Path, content: str = BLOCK, head: str = "") -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        txt = path.read_text(encoding="utf-8")
        if LEGACY_BEGIN in txt and LEGACY_END in txt:  # migrate the old block in place
            new = re.sub(re.escape(LEGACY_BEGIN) + r".*?" + re.escape(LEGACY_END) + r"\n?", lambda m: content, txt, flags=re.S)
            path.write_text(new, encoding="utf-8")
            return "migrated"
        if BEGIN in txt and END in txt:
            new = re.sub(re.escape(BEGIN) + r".*?" + re.escape(END) + r"\n?", lambda m: content, txt, flags=re.S)
            if new == txt:
                return "unchanged"
            path.write_text(new, encoding="utf-8")
            return "updated"
        path.write_text(txt.rstrip("\n") + "\n\n" + content, encoding="utf-8")
        return "appended"
    path.write_text(head + content, encoding="utf-8")
    return "created"


def remove_block(path: Path) -> bool:
    if not path.exists():
        return False
    txt = path.read_text(encoding="utf-8")
    if BEGIN not in txt and LEGACY_BEGIN not in txt:
        return False
    new = txt
    for b, e in ((BEGIN, END), (LEGACY_BEGIN, LEGACY_END)):
        new = re.sub(r"\n*" + re.escape(b) + r".*?" + re.escape(e) + r"\n?", "\n", new, flags=re.S)
    new = new.strip("\n")
    if not new or new.startswith("---") and new.count("---") == 2 and ("ganjineh" in new or "gonjineh" in new):
        path.unlink()
    else:
        path.write_text(new + "\n", encoding="utf-8")
    return True


def _load_json(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _dump_json(p: Path, d: dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def claude_hooks(root: Path, local: bool = False, prompt_recall: bool = True) -> str:
    p = root / ".claude" / ("settings.local.json" if local else "settings.json")
    d = _load_json(p)
    hooks = d.setdefault("hooks", {})
    cmd = f"{exe()} hook claude"
    for ev in CLAUDE_EVENTS:
        if ev == "UserPromptSubmit" and not prompt_recall:
            continue
        arr = hooks.setdefault(ev, [])
        arr[:] = [g for g in arr if not any(m in (h.get("command") or "") for m in HOOK_MARKS for h in g.get("hooks", []))]
        arr.append({"hooks": [{"type": "command", "command": cmd, "timeout": 20}]})
    _dump_json(p, d)
    return str(p)


def remove_claude_hooks(root: Path) -> None:
    for name in ("settings.json", "settings.local.json"):
        p = root / ".claude" / name
        if not p.exists():
            continue
        d = _load_json(p)
        hooks = d.get("hooks", {})
        for ev in list(hooks):
            hooks[ev] = [g for g in hooks[ev] if not any(m in (h.get("command") or "") for m in HOOK_MARKS for h in g.get("hooks", []))]
            if not hooks[ev]:
                del hooks[ev]
        if not hooks:
            d.pop("hooks", None)
        if d:
            _dump_json(p, d)
        else:
            p.unlink()


def mcp_json(path: Path, key: str = "mcpServers", vscode: bool = False) -> str:
    d = _load_json(path)
    entry = {"command": exe().split()[0], "args": exe().split()[1:] + ["mcp"]}
    if vscode:
        entry = {"type": "stdio", **entry}
    d.setdefault(key, {}).pop("gonjineh", None)  # drop the pre-0.1.1 entry
    d[key]["ganjineh"] = entry
    _dump_json(path, d)
    return str(path)


def remove_mcp_json(path: Path, key: str = "mcpServers") -> None:
    if not path.exists():
        return
    d = _load_json(path)
    d.get(key, {}).pop("ganjineh", None)
    d.get(key, {}).pop("gonjineh", None)
    if not d.get(key):
        d.pop(key, None)
    if d:
        _dump_json(path, d)
    else:
        path.unlink()


CODEX_BEGIN, CODEX_END = "# >>> ganjineh (managed) >>>", "# <<< ganjineh (managed) <<<"


def codex_config(config_path: Path, with_mcp: bool = True) -> str:
    """Add `notify` (top level, must precede tables) and an MCP server entry to ~/.codex/config.toml between markers."""
    txt = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    for b, e in ((CODEX_BEGIN, CODEX_END), (LEGACY_CODEX_BEGIN, LEGACY_CODEX_END)):
        txt = re.sub(re.escape(b) + r".*?" + re.escape(e) + r"\n?", "", txt, flags=re.S)
    parts = exe().split()
    has_notify = re.search(r"^\s*notify\s*=", txt, re.M) is not None
    status = "ok"
    top = ""
    if not has_notify:
        top = f"{CODEX_BEGIN}\nnotify = {json.dumps(parts + ['hook', 'codex'])}\n{CODEX_END}\n"
    else:
        status = "notify-already-set (left untouched; chain `ganjineh hook codex` yourself)"
    tail = ""
    if with_mcp and "[mcp_servers.ganjineh]" not in txt:
        tail = f"\n{CODEX_BEGIN}\n[mcp_servers.ganjineh]\ncommand = {json.dumps(parts[0])}\nargs = {json.dumps(parts[1:] + ['mcp'])}\n{CODEX_END}\n"
    if config_path.exists():
        shutil.copy(config_path, str(config_path) + ".ganjineh.bak")
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(top + txt.rstrip("\n") + ("\n" if txt.strip() else "") + tail, encoding="utf-8")
    return status


def remove_codex_config(config_path: Path) -> None:
    if config_path.exists():
        txt = config_path.read_text(encoding="utf-8")
        for b, e in ((CODEX_BEGIN, CODEX_END), (LEGACY_CODEX_BEGIN, LEGACY_CODEX_END)):
            txt = re.sub(re.escape(b) + r".*?" + re.escape(e) + r"\n?", "", txt, flags=re.S)
        config_path.write_text(txt.strip("\n") + "\n" if txt.strip() else "", encoding="utf-8")


def install_project(root: Path, *, claude=True, local_hooks=False, prompt_recall=True, mcp=True) -> dict:
    out = {}
    if (root / LEGACY_MDC).exists():  # old Cursor rule file: replaced by ganjineh.mdc
        remove_block(root / LEGACY_MDC)
        if (root / LEGACY_MDC).exists():
            (root / LEGACY_MDC).unlink()
        out[LEGACY_MDC] = "removed (renamed to ganjineh.mdc)"
    for rel in INSTRUCTION_FILES:
        p = root / rel
        out[rel] = write_block(p, BLOCK, MDC_HEAD if rel.endswith(".mdc") else "")
    if claude:
        out[".claude hooks"] = claude_hooks(root, local_hooks, prompt_recall)
    if mcp:
        out[".mcp.json"] = mcp_json(root / ".mcp.json")
        out[".cursor/mcp.json"] = mcp_json(root / ".cursor" / "mcp.json")
        out[".gemini/settings.json"] = mcp_json(root / ".gemini" / "settings.json")
        out[".vscode/mcp.json"] = mcp_json(root / ".vscode" / "mcp.json", key="servers", vscode=True)
    return out


def uninstall_project(root: Path) -> None:
    for rel in (*INSTRUCTION_FILES, LEGACY_MDC):
        remove_block(root / rel)
    remove_claude_hooks(root)
    for rel, key in ((".mcp.json", "mcpServers"), (".cursor/mcp.json", "mcpServers"), (".gemini/settings.json", "mcpServers"), (".vscode/mcp.json", "servers")):
        remove_mcp_json(root / rel, key)
