"""gonjineh command line."""
from __future__ import annotations
import argparse
import json
import os
import sys
import time
from pathlib import Path

from . import __version__, brain, core, digest, hooks, installer, store, transcripts
from .scrub import scrub, Report


def _ctx(args):
    return core.Ctx.load(getattr(args, "cwd", None))


def cmd_init(a):
    root = Path(a.cwd or os.getcwd()).resolve()
    pf = root / brain.PROJECT_FILE
    if pf.exists():
        cfg = json.loads(pf.read_text())
        if a.brain and a.brain != cfg.get("brain"):
            cfg["brain"] = a.brain
        if a.project:
            cfg["project"] = a.project
    else:
        cfg = {"schema": 1, "project": a.project or root.name, "brain": a.brain or "", "areas": {}, "pii": True}
    pf.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n")
    ucfg = brain.user_config()
    author = a.author or ucfg.get("author") or brain.default_author()
    ucfg["author"] = author
    up = ucfg.setdefault("projects", {}).setdefault(cfg["project"], {})
    bpath = Path(a.brain_path) if a.brain_path else brain.brain_dir_for(cfg["brain"], cfg["project"])
    up["brain"] = str(bpath)
    up["author"] = author
    if a.area:
        up["area"] = a.area
    brain.save_user_config(ucfg)
    status = brain.ensure_brain(bpath, cfg["brain"] or None)
    print(f"brain: {bpath} ({status})")
    res = installer.install_project(root, claude=not a.no_claude, local_hooks=a.local_hooks, prompt_recall=not a.no_prompt_recall, mcp=not a.no_mcp)
    for k, v in res.items():
        print(f"  {k}: {v}")
    if a.codex:
        cp = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex") / "config.toml"
        print(f"  codex ({cp}): {installer.codex_config(cp)}")
    else:
        print("  codex: skipped (it is user-level config; run `gonjineh init --codex` to add notify + MCP to ~/.codex/config.toml)")
    gi = root / ".gitignore"
    print("next: commit .gonjineh.json, CLAUDE.md, AGENTS.md etc. so teammates get the same setup; each teammate runs `gonjineh init` once.")
    return 0


def cmd_capture(a):
    ctx = _ctx(a)
    paths = []
    if a.file:
        paths = [Path(a.file)]
    elif a.latest:
        home = os.path.expanduser("~")
        cands = list(transcripts.claude_project_dir(str(ctx.root), home).glob("*.jsonl"))
        cx = Path(os.environ.get("CODEX_HOME") or Path(home) / ".codex") / "sessions"
        if cx.exists():
            cands += [p for p in cx.rglob("rollout-*.jsonl") if str(ctx.root) in p.read_text(errors="replace")[:4000]]
        if not cands:
            print("no transcripts found for this project", file=sys.stderr)
            return 1
        paths = [max(cands, key=lambda p: p.stat().st_mtime)]
    elif a.all:
        home = os.path.expanduser("~")
        paths = list(transcripts.claude_project_dir(str(ctx.root), home).glob("*.jsonl"))
        cx = Path(os.environ.get("CODEX_HOME") or Path(home) / ".codex") / "sessions"
        if cx.exists():
            paths += [p for p in cx.rglob("rollout-*.jsonl") if str(ctx.root) in p.read_text(errors="replace")[:4000]]
    else:
        print("give --file PATH, --latest or --all", file=sys.stderr)
        return 2
    for p in paths:
        r = core.capture_file(ctx, p, a.format, a.detail)
        print(f"{p.name}: " + (f"stored {r['id']} area={r['area']} files={r['files']} redactions={r['redactions'] or 0}" if r["stored"] else r["reason"]))
    if a.sync:
        print(json.dumps(brain.sync(ctx.brain)))
    return 0


def cmd_note(a):
    ctx = _ctx(a)
    text = a.text if a.text != "-" else sys.stdin.read()
    r = core.add_note(ctx, text, a.title or "", a.area or "", a.file, a.tag)
    print(f"saved {r['id']} area={r['area']}" + (f" redacted={r['redactions']}" if r["redactions"] else ""))
    if a.sync:
        print(json.dumps(brain.sync(ctx.brain)))
    return 0


def cmd_sync(a):
    ctx = _ctx(a)
    if a.after:
        tok = f"{time.time():.6f}"
        core.state_set(f"sync:{ctx.brain}", tok)
        time.sleep(a.after)
        if core.state_get(f"sync:{ctx.brain}") != tok:
            return 0  # a newer event will sync
    lock = brain.home() / "locks" / (ctx.brain.name + ".lock")
    lock.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.time() + 60
    while True:
        try:
            os.mkdir(lock)
            break
        except FileExistsError:
            try:
                if time.time() - lock.stat().st_mtime > 120:
                    os.rmdir(lock)
                    continue
            except OSError:
                pass
            if time.time() > deadline:
                return 0
            time.sleep(0.2)
    try:
        r = brain.sync(ctx.brain)
        ctx.reindex()
    finally:
        try:
            os.rmdir(lock)
        except OSError:
            pass
    if not a.quiet:
        print(json.dumps(r))
    return 0 if not r["error"] or "offline" in r["error"] else 1


def _fmt_hit(h):
    s = f"[{h['id']}] {h['date']} {h['author']} ({h['tool']}) · {h['area']} · {h['title']}  (score {h['score']})"
    if h.get("files"):
        s += "\n    files: " + ", ".join(h["files"][:5])
    if h.get("endpoints"):
        s += "\n    api:   " + ", ".join(h["endpoints"][:5])
    if h.get("decisions"):
        s += "\n    decision: " + h["decisions"][0][:160]
    return s


def cmd_search(a):
    ctx = _ctx(a)
    if a.pull:
        brain.pull_only(ctx.brain)
    hits = store.search(ctx.entries(a.all_projects), " ".join(a.query), a.limit, a.area, a.author)
    if a.json:
        print(json.dumps([{k: v for k, v in h.items() if k not in ("body",)} for h in hits], ensure_ascii=False, indent=2))
    else:
        print("\n".join(_fmt_hit(h) for h in hits) or "no matches")
    return 0


def cmd_recall(a):
    ctx = _ctx(a)
    txt = store.briefing(ctx.entries(), ctx.author)
    print(txt or "brain is empty")
    return 0


def cmd_who(a):
    ctx = _ctx(a)
    res = store.who_knows(ctx.entries(), a.target)
    for r in res:
        print(f"{r['author']}: {r['entries']} entries (last {r['last']}; {', '.join(r['tools'])})")
    if not res:
        print("nobody has recorded work on that")
    return 0


def cmd_index(a):
    ctx = _ctx(a)
    ctx.reindex()
    print(ctx.brain / "INDEX.md")
    return 0


def cmd_show(a):
    ctx = _ctx(a)
    e = core.read_entry(ctx, a.id)
    if not e:
        print("not found", file=sys.stderr)
        return 1
    print((ctx.brain / e["path"]).read_text(encoding="utf-8"))
    return 0


def cmd_scrub(a):
    text = sys.stdin.read() if a.file == "-" else Path(a.file).read_text(encoding="utf-8", errors="replace")
    rep = Report()
    sys.stdout.write(scrub(text, report=rep))
    print(f"\n[gonjineh] {rep.total} redaction(s): {rep.counts}", file=sys.stderr)
    return 0


def cmd_watch(a):
    ctx = _ctx(a)
    print(f"watching: sync every {a.interval}s (Ctrl-C to stop)")
    seen: dict = {}
    home = os.path.expanduser("~")
    try:
        while True:
            paths = list(transcripts.claude_project_dir(str(ctx.root), home).glob("*.jsonl"))
            cx = Path(os.environ.get("CODEX_HOME") or Path(home) / ".codex") / "sessions"
            if cx.exists():
                paths += [p for p in cx.rglob("rollout-*.jsonl") if str(ctx.root) in p.read_text(errors="replace")[:4000]]
            for p in paths:
                m = p.stat().st_mtime
                if seen.get(p) != m and time.time() - m > a.settle:
                    seen[p] = m
                    r = core.capture_file(ctx, p)
                    if r["stored"]:
                        print(f"captured {p.name} -> {r['id']}")
            r = brain.sync(ctx.brain)
            ctx.reindex()
            if r["error"]:
                print("sync:", r["error"])
            time.sleep(a.interval)
    except KeyboardInterrupt:
        return 0


def cmd_hook(a):
    if a.which == "claude":
        return hooks.claude(sys.stdin.read())
    return hooks.codex(a.payload[-1] if a.payload else "")


def cmd_mcp(a):
    from . import mcp
    mcp.serve(a.cwd)
    return 0


def cmd_doctor(a):
    ok = True
    try:
        ctx = _ctx(a)
    except core.NoProject as e:
        print("project:  ✗", e)
        return 1
    print(f"project:  ✓ {ctx.project} ({ctx.root})")
    print(f"author:   {ctx.author}  default area: {ctx.default_area}")
    print(f"brain:    {'✓' if (ctx.brain/'.git').exists() else '✗'} {ctx.brain}  remote: {'yes' if brain.has_remote(ctx.brain) else 'NO (local only; add one so teammates see it)'}")
    print(f"entries:  {len(ctx.entries())}")
    cs = ctx.root / ".claude" / "settings.json"
    cl = ctx.root / ".claude" / "settings.local.json"
    has = any(p.exists() and installer.HOOK_MARK in p.read_text() for p in (cs, cl))
    print(f"claude hooks: {'✓' if has else '✗ (run gonjineh init)'}")
    cc = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex") / "config.toml"
    print(f"codex notify: {'✓' if cc.exists() and installer.CODEX_BEGIN in cc.read_text() else '– (optional: gonjineh init --codex)'}")
    for rel in installer.INSTRUCTION_FILES:
        p = ctx.root / rel
        print(f"  {rel}: {'✓' if p.exists() and installer.BEGIN in p.read_text() else '✗'}")
    return 0


def cmd_uninstall(a):
    root = Path(a.cwd or os.getcwd()).resolve()
    installer.uninstall_project(root)
    if a.codex:
        installer.remove_codex_config(Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex") / "config.toml")
    print("removed managed blocks, hooks and MCP entries (the brain repo and .gonjineh.json were kept)")
    return 0


def build_parser():
    p = argparse.ArgumentParser(prog="gonjineh", description="Git-native shared memory for your team's AI coding agents.")
    p.add_argument("--version", action="version", version=f"gonjineh {__version__}")
    p.add_argument("--cwd", help=argparse.SUPPRESS)
    sub = p.add_subparsers(dest="cmd", required=True)

    def add(name, fn, help):
        sp = sub.add_parser(name, help=help)
        sp.add_argument("--cwd", help=argparse.SUPPRESS, default=argparse.SUPPRESS)
        sp.set_defaults(fn=fn)
        return sp
    s = add("init", cmd_init, "set up this project: brain repo, instruction files, Claude hooks, MCP config")
    s.add_argument("--brain", help="git URL (or path) of the shared brain repo")
    s.add_argument("--brain-path", help="where to keep the local clone")
    s.add_argument("--project"); s.add_argument("--author"); s.add_argument("--area", help="your default area, e.g. frontend")
    s.add_argument("--codex", action="store_true", help="also edit ~/.codex/config.toml (notify + MCP)")
    s.add_argument("--no-claude", action="store_true"); s.add_argument("--no-mcp", action="store_true")
    s.add_argument("--no-prompt-recall", action="store_true", help="do not inject related teammate work on every prompt")
    s.add_argument("--local-hooks", action="store_true", help="write hooks to .claude/settings.local.json (not shared)")
    s = add("capture", cmd_capture, "digest a transcript into the brain")
    s.add_argument("--file"); s.add_argument("--latest", action="store_true"); s.add_argument("--all", action="store_true")
    s.add_argument("--format", default="auto", choices=["auto", "claude", "codex", "generic"])
    s.add_argument("--detail", default="normal", choices=["normal", "low"]); s.add_argument("--sync", action="store_true")
    s = add("note", cmd_note, "add a manual note (use - to read stdin)")
    s.add_argument("text"); s.add_argument("--title"); s.add_argument("--area"); s.add_argument("--file", action="append"); s.add_argument("--tag", action="append"); s.add_argument("--sync", action="store_true")
    s = add("sync", cmd_sync, "pull --rebase, commit, push the brain")
    s.add_argument("--quiet", action="store_true"); s.add_argument("--after", type=float, default=0, help="debounce: wait N seconds, skip if a newer sync was requested")
    s = add("search", cmd_search, "search the team memory")
    s.add_argument("query", nargs="+"); s.add_argument("--area"); s.add_argument("--author"); s.add_argument("--limit", type=int, default=6)
    s.add_argument("--all-projects", action="store_true"); s.add_argument("--json", action="store_true"); s.add_argument("--pull", action="store_true")
    s = add("recall", cmd_recall, "print the short briefing injected at session start")
    s = add("who", cmd_who, "who worked on a file, endpoint or area")
    s.add_argument("target")
    s = add("index", cmd_index, "rebuild INDEX.md locally")
    s = add("show", cmd_show, "print one entry")
    s.add_argument("id")
    s = add("scrub", cmd_scrub, "run the secret scrubber over a file (- for stdin) and print the result")
    s.add_argument("file")
    s = add("watch", cmd_watch, "poll transcripts and sync (for tools without hooks)")
    s.add_argument("--interval", type=int, default=60); s.add_argument("--settle", type=int, default=20)
    s = add("hook", cmd_hook, "internal: entry point for agent hooks")
    s.add_argument("which", choices=["claude", "codex"]); s.add_argument("payload", nargs="*")
    s = add("mcp", cmd_mcp, "run the MCP server on stdio")
    s = add("doctor", cmd_doctor, "check the setup")
    s = add("uninstall", cmd_uninstall, "remove what init added")
    s.add_argument("--codex", action="store_true")
    return p


def main(argv=None):
    a = build_parser().parse_args(argv)
    if not hasattr(a, "cwd"):
        a.cwd = None
    try:
        return a.fn(a)
    except core.NoProject as e:
        print(f"gonjineh: {e}", file=sys.stderr)
        return 1
    except RuntimeError as e:
        print(f"gonjineh: {e}", file=sys.stderr)
        return 1
