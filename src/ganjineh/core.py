"""High-level operations shared by the CLI, the hooks and the MCP server."""
from __future__ import annotations
import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import brain, digest, store, transcripts
from .scrub import Report, scrub


class NoProject(Exception):
    pass


@dataclass
class Ctx:
    root: Path
    project: str
    brain: Path
    author: str
    default_area: str = "general"
    area_rules: list = field(default_factory=list)
    ignore: list = field(default_factory=list)
    pii: bool = True
    mask_email: bool = False

    @classmethod
    def load(cls, cwd=None):
        import os
        root = brain.find_project_root(cwd)
        if root is None:
            raise NoProject("no .ganjineh.json found in this directory or any parent; run `ganjineh init`")
        cfg = brain.load_project(root)
        ucfg = brain.user_config()
        proj = cfg["project"]
        up = (ucfg.get("projects") or {}).get(proj, {})
        bpath = Path(up.get("brain") or brain.env("BRAIN") or brain.brain_dir_for(cfg.get("brain", ""), proj))
        rules = [(a, g if isinstance(g, list) else [g]) for a, g in (cfg.get("areas") or {}).items()] or None
        ignore = []
        for p in (root / n for n in brain.IGNORE_FILES):
            if p.exists():
                ignore += digest.load_ignore(p.read_text(encoding="utf-8"))
        return cls(root=root, project=proj, brain=bpath, author=up.get("author") or brain.default_author(),
                   default_area=up.get("area") or cfg.get("default_area") or "general",
                   area_rules=rules or digest.DEFAULT_AREAS, ignore=ignore, pii=cfg.get("pii", True), mask_email=cfg.get("mask_email", False))

    def entries(self, all_projects=False):
        return store.load_all(self.brain, None if all_projects else self.project)

    def reindex(self):
        txt = store.build_index(self.entries(), self.project)
        (self.brain / "INDEX.md").write_text(txt, encoding="utf-8")


def capture_session(ctx: Ctx, session, detail="normal") -> dict:
    built = digest.build_entry(session, author=ctx.author, project=ctx.project, area_rules=ctx.area_rules,
                               default_area=ctx.default_area, ignore_patterns=ctx.ignore, detail=detail, pii=ctx.pii, mask_email=ctx.mask_email)
    if built is None:
        return {"stored": False, "reason": "skipped (private, ignored files, or no signal)"}
    entry, rep = built
    p = store.write_entry(ctx.brain, entry)
    brain.commit_local(ctx.brain, f"ganjineh: {entry['author']} {entry['tool']} {entry['area']}: {entry['title'][:60]}")
    ctx.reindex()
    return {"stored": True, "path": str(p), "id": entry["id"], "area": entry["area"], "redactions": rep.counts, "files": len(entry["files"])}


def capture_file(ctx: Ctx, path, fmt="auto", detail="normal") -> dict:
    return capture_session(ctx, transcripts.read_any(path, fmt), detail)


def add_note(ctx: Ctx, text: str, title: str = "", area: str = "", files=None, tags=None, tool="note") -> dict:
    from datetime import datetime, timezone
    import hashlib
    rep = Report()
    text_c = scrub(text, pii=ctx.pii, mask_email=ctx.mask_email, report=rep)
    title_c = scrub(title or text.strip().splitlines()[0][:90], pii=ctx.pii, mask_email=ctx.mask_email, report=rep)
    now = datetime.now(timezone.utc)
    eid = hashlib.sha1(f"note:{ctx.author}:{now.isoformat()}:{text}".encode()).hexdigest()[:10]
    files = [f for f in (files or []) if not digest.ignored(f, ctx.ignore)]
    entry = {"id": eid, "title": title_c, "author": ctx.author, "tool": tool, "session": "note", "date": now.strftime("%Y-%m-%d"),
             "project": ctx.project, "area": area or (digest.infer_areas(files, ctx.area_rules, ctx.default_area)[0]),
             "files": files, "tags": [scrub(t) for t in (tags or [])], "text": text_c, "turns": 0}
    entry["areas"] = [entry["area"]]
    entry["endpoints"] = []
    for rx in digest.ENDPOINT:
        for m in rx.finditer(text_c):
            g = [x for x in m.groups() if x]
            e = ((g[-2].upper() + " " + g[-1]) if len(g) >= 2 else g[-1]).rstrip(".,;:)'\"`")
            if e not in entry["endpoints"]:
                entry["endpoints"].append(e)
    p = store.write_entry(ctx.brain, entry)
    brain.commit_local(ctx.brain, f"ganjineh: note by {ctx.author}: {title_c[:60]}")
    ctx.reindex()
    return {"stored": True, "id": eid, "path": str(p), "area": entry["area"], "redactions": rep.counts}


def read_entry(ctx: Ctx, eid: str):
    for e in ctx.entries(all_projects=True):
        if e["id"].startswith(eid):
            return e
    return None


# ---- throttling / debounce state -------------------------------------------------

def _state_path():
    return brain.home() / "state.json"


def state_get(key, default=0.0):
    try:
        return json.loads(_state_path().read_text()).get(key, default)
    except (OSError, ValueError):
        return default


def state_set(key, value):
    try:
        d = json.loads(_state_path().read_text())
    except (OSError, ValueError):
        d = {}
    d[key] = value
    brain.home().mkdir(parents=True, exist_ok=True)
    tmp = _state_path().with_suffix(".tmp")
    tmp.write_text(json.dumps(d))
    tmp.replace(_state_path())
