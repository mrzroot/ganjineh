"""Minimal MCP server over stdio (newline-delimited JSON-RPC 2.0). No dependencies."""
from __future__ import annotations
import json
import sys

from . import __version__, brain, core, store

PROTOCOLS = ["2025-06-18", "2025-03-26", "2024-11-05"]

TOOLS = [
    {"name": "search_memory",
     "description": "Search the team's shared AI-session memory (what teammates built, decided, and which files/endpoints they touched). Call this BEFORE assuming a feature, endpoint or component does or does not exist.",
     "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}, "area": {"type": "string", "description": "e.g. frontend, backend"}, "limit": {"type": "integer", "default": 6}}, "required": ["query"]}},
    {"name": "read_entry",
     "description": "Read one memory entry in full by id (prefix is enough).",
     "inputSchema": {"type": "object", "properties": {"id": {"type": "string"}}, "required": ["id"]}},
    {"name": "add_note",
     "description": "Record a decision, contract or gotcha for teammates' AIs. Never include secrets.",
     "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}, "title": {"type": "string"}, "area": {"type": "string"}, "files": {"type": "array", "items": {"type": "string"}}, "tags": {"type": "array", "items": {"type": "string"}}}, "required": ["text"]}},
    {"name": "who_knows_about",
     "description": "Who worked on a file path, endpoint or area (e.g. 'src/api/users.py', '/api/login', 'backend').",
     "inputSchema": {"type": "object", "properties": {"target": {"type": "string"}}, "required": ["target"]}},
    {"name": "recent",
     "description": "Latest entries by teammates, optionally for one area.",
     "inputSchema": {"type": "object", "properties": {"area": {"type": "string"}, "limit": {"type": "integer", "default": 8}}}},
]


def _short(e: dict) -> str:
    s = f"[{e['id']}] {e.get('date','')} {e['author']} ({e['tool']}) · {e.get('area','')} · {e['title']}"
    if e.get("files"):
        s += "\n  files: " + ", ".join(e["files"][:6])
    if e.get("endpoints"):
        s += "\n  api: " + ", ".join(e["endpoints"][:6])
    if e.get("decisions"):
        s += "\n  decision: " + e["decisions"][0][:200]
    return s


def call_tool(ctx: core.Ctx, name: str, args: dict) -> str:
    if name == "search_memory":
        brain.pull_only(ctx.brain) if args.get("refresh") else None
        hits = store.search(ctx.entries(), args.get("query", ""), limit=int(args.get("limit") or 6), area=args.get("area"))
        return "\n".join(_short(h) + f"  (score {h['score']})" for h in hits) or "No matching memory. Nothing recorded about this yet."
    if name == "read_entry":
        e = core.read_entry(ctx, args.get("id", ""))
        return (Path_text(ctx, e) if e else "Not found.")
    if name == "add_note":
        r = core.add_note(ctx, args["text"], args.get("title", ""), args.get("area", ""), args.get("files"), args.get("tags"), tool="mcp-note")
        from . import hooks
        hooks.spawn_sync(str(ctx.root), after=20)
        return f"Saved entry {r['id']} in area {r['area']}" + (f" (redacted: {r['redactions']})" if r["redactions"] else "")
    if name == "who_knows_about":
        res = store.who_knows(ctx.entries(), args.get("target", ""))
        return "\n".join(f"{a['author']}: {a['entries']} entries, last {a['last']}, tools {', '.join(a['tools'])}, ids {', '.join(a['ids'][:3])}" for a in res) or "Nobody has recorded work on that."
    if name == "recent":
        es = sorted(ctx.entries(), key=lambda e: (e.get("date", ""), e["id"]), reverse=True)
        if args.get("area"):
            es = [e for e in es if args["area"] in (e.get("areas") or [e.get("area")])]
        return "\n".join(_short(e) for e in es[: int(args.get("limit") or 8)]) or "Empty brain."
    raise KeyError(name)


def Path_text(ctx, e):
    from pathlib import Path
    return (ctx.brain / e["path"]).read_text(encoding="utf-8")


def handle(msg: dict, ctx_factory):
    mid, method = msg.get("id"), msg.get("method")
    params = msg.get("params") or {}
    if method == "initialize":
        want = params.get("protocolVersion")
        ver = want if want in PROTOCOLS else PROTOCOLS[0]
        return {"jsonrpc": "2.0", "id": mid, "result": {"protocolVersion": ver, "capabilities": {"tools": {}},
                                                       "serverInfo": {"name": "gonjineh", "version": __version__}}}
    if method == "ping":
        return {"jsonrpc": "2.0", "id": mid, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": mid, "result": {"tools": TOOLS}}
    if method == "tools/call":
        try:
            ctx = ctx_factory()
            text = call_tool(ctx, params.get("name", ""), params.get("arguments") or {})
            return {"jsonrpc": "2.0", "id": mid, "result": {"content": [{"type": "text", "text": text}]}}
        except core.NoProject as e:
            return {"jsonrpc": "2.0", "id": mid, "result": {"isError": True, "content": [{"type": "text", "text": str(e)}]}}
        except KeyError:
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32602, "message": f"unknown tool {params.get('name')}"}}
        except Exception as e:
            return {"jsonrpc": "2.0", "id": mid, "result": {"isError": True, "content": [{"type": "text", "text": f"error: {e}"}]}}
    if mid is None:
        return None  # notification
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"method not found: {method}"}}


def serve(cwd=None, fin=sys.stdin, fout=sys.stdout):
    import os
    cwd = cwd or os.environ.get("GONJINEH_PROJECT") or os.getcwd()
    for line in fin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            fout.write(json.dumps({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}}) + "\n")
            fout.flush()
            continue
        resp = handle(msg, lambda: core.Ctx.load(cwd))
        if resp is not None:
            fout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            fout.flush()
