"""Entries on disk (one markdown file per session, so teammates never edit the same file), BM25 search, INDEX.md."""
from __future__ import annotations
import json
import math
import os
import re
from collections import Counter
from pathlib import Path

from .textnorm import tokenize

LISTS = ("areas", "files", "endpoints", "tags", "asks", "decisions", "gotchas", "todos", "commands")
ORDER = ["id", "title", "author", "tool", "session", "date", "project", "area", "areas", "branch", "files", "endpoints", "tags", "turns"]


def slug(s: str, n: int = 40) -> str:
    s = re.sub(r"[^\w]+", "-", s.strip().lower(), flags=re.U).strip("-")
    return (s[:n].strip("-")) or "entry"


def render(e: dict) -> str:
    head = ["---"]
    for k in ORDER:
        if k in e and e[k] not in ("", None):
            head.append(f"{k}: {json.dumps(e[k], ensure_ascii=False)}")
    head.append("---")
    body = [f"# {e['title']}", ""]
    body.append(f"> **{e['author']}** · {e['tool']} · {e['date']} · area: **{e['area']}**" + (f" · branch `{e['branch']}`" if e.get("branch") else ""))
    body.append("")

    def sec(name, items, bullet=True, code=False):
        if not items:
            return
        body.append(f"## {name}")
        for it in items:
            body.append(f"- `{it}`" if code else (f"- {it}" if bullet else it))
        body.append("")
    if e.get("outcome"):
        body += ["## Outcome", e["outcome"], ""]
    sec("What was asked", e.get("asks"))
    sec("Decisions", e.get("decisions"))
    sec("Files touched", e.get("files"), code=True)
    sec("API / contracts", e.get("endpoints"), code=True)
    sec("Gotchas", e.get("gotchas"))
    sec("Open TODOs", e.get("todos"))
    sec("Commands", e.get("commands"), code=True)
    if e.get("text"):
        body += ["## Note", e["text"], ""]
    return "\n".join(head + [""] + body).rstrip() + "\n"


def parse(text: str) -> dict:
    e: dict = {}
    m = re.match(r"---\n(.*?)\n---\n(.*)", text, re.S)
    if not m:
        return {"title": text.splitlines()[0] if text else "", "body": text}
    for line in m.group(1).splitlines():
        if ": " in line:
            k, v = line.split(": ", 1)
            try:
                e[k] = json.loads(v)
            except ValueError:
                e[k] = v
    body = m.group(2)
    e["body"] = body
    sections = re.split(r"^## ", body, flags=re.M)
    for sec in sections[1:]:
        name, _, rest = sec.partition("\n")
        items = [re.sub(r"^- `?(.*?)`?$", r"\1", l) for l in rest.splitlines() if l.startswith("- ")]
        key = {"What was asked": "asks", "Decisions": "decisions", "Files touched": "files", "API / contracts": "endpoints",
               "Gotchas": "gotchas", "Open TODOs": "todos", "Commands": "commands"}.get(name.strip())
        if key and key not in e:
            e[key] = items
        elif name.strip() == "Outcome":
            e["outcome"] = rest.strip()
        elif name.strip() == "Note":
            e["text"] = rest.strip()
    return e


def entry_path(root: Path, e: dict) -> Path:
    fname = f"{e['date']}-{slug(e['author'], 16)}-{slug(e['tool'], 12)}-{e['id']}.md"
    return Path(root) / "entries" / slug(e["project"], 40) / slug(e["area"], 24) / fname


def write_entry(root: Path, e: dict) -> Path:
    p = entry_path(root, e)
    # one entry id lives in exactly one place: remove an older copy if its area/date changed
    for old in Path(root).glob(f"entries/*/*/*-{e['id']}.md"):
        if old != p:
            old.unlink()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(render(e), encoding="utf-8")
    return p


def load_all(root: Path, project: str | None = None) -> list[dict]:
    out = []
    base = Path(root) / "entries"
    if not base.exists():
        return out
    for p in sorted(base.rglob("*.md")):
        try:
            e = parse(p.read_text(encoding="utf-8"))
        except OSError:
            continue
        if not e.get("id"):
            continue
        if project and e.get("project") != project:
            continue
        e["path"] = str(p.relative_to(root))
        out.append(e)
    return out


FIELD_W = {"title": 3.0, "tags": 3.0, "files": 2.5, "endpoints": 2.5, "decisions": 1.6, "gotchas": 1.6, "outcome": 1.3, "asks": 1.2, "todos": 1.0, "text": 1.4, "area": 2.0, "author": 1.0, "commands": 0.6}


def _fields(e: dict) -> Counter:
    c: Counter = Counter()
    for k, w in FIELD_W.items():
        v = e.get(k)
        if not v:
            continue
        txt = " ".join(v) if isinstance(v, list) else str(v)
        for t in tokenize(txt):
            c[t] += w
    return c


def search(entries: list[dict], query: str, limit: int = 8, area: str | None = None, author: str | None = None):
    q = tokenize(query)
    if not q:
        return []
    pool = [e for e in entries if (not area or area in (e.get("areas") or [e.get("area")])) and (not author or e.get("author") == author)]
    if not pool:
        return []
    docs = [_fields(e) for e in pool]
    lens = [sum(d.values()) or 1 for d in docs]
    avg = sum(lens) / len(lens)
    n = len(pool)
    df: Counter = Counter()
    for d in docs:
        for t in set(d):
            df[t] += 1
    # prefix expansion so "auth" finds "authentication" and "login" finds "logins"
    vocab = set(df)
    expanded = []
    for t in q:
        exp = [(t, 1.0)] if t in vocab else []
        if len(t) >= 3:
            exp += [(v, 0.6) for v in vocab if v != t and (v.startswith(t) or (len(v) >= 4 and t.startswith(v)))][:6]
        expanded.append(exp)
    k1, b = 1.4, 0.75
    scored = []
    for e, d, ln in zip(pool, docs, lens):
        sc = 0.0
        for exp in expanded:
            for t, wt in exp:
                f = d.get(t, 0)
                if f:
                    idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
                    sc += wt * idf * (f * (k1 + 1)) / (f + k1 * (1 - b + b * ln / avg))
        if sc > 0:
            scored.append((sc, e))
    scored.sort(key=lambda x: -x[0])
    return [dict(e, score=round(s, 3)) for s, e in scored[:limit]]


def who_knows(entries: list[dict], target: str, limit: int = 5):
    """Rank authors by how many entries touch a file path / endpoint / area matching *target*."""
    t = target.lower()
    by: dict[str, dict] = {}
    for e in entries:
        hit = any(t in f.lower() for f in e.get("files", [])) or any(t in x.lower() for x in e.get("endpoints", [])) \
            or t == (e.get("area") or "").lower() or t in (e.get("title") or "").lower()
        if hit:
            a = by.setdefault(e["author"], {"author": e["author"], "entries": 0, "last": "", "tools": set(), "ids": []})
            a["entries"] += 1
            a["last"] = max(a["last"], e.get("date", ""))
            a["tools"].add(e.get("tool", ""))
            a["ids"].append(e["id"])
    out = sorted(by.values(), key=lambda a: (-a["entries"], a["author"]))
    for a in out:
        a["tools"] = sorted(a["tools"])
    return out[:limit]


def build_index(entries: list[dict], project: str | None = None, me: str | None = None) -> str:
    es = sorted(entries, key=lambda e: (e.get("date", ""), e.get("id", "")), reverse=True)
    lines = ["# Team brain index", "",
             "_Generated locally by gonjineh; do not edit. Ask `gonjineh search <words>` or use the MCP tool `search_memory`._", ""]
    if project:
        lines += [f"Project: **{project}**", ""]
    areas: dict[str, list] = {}
    for e in es:
        areas.setdefault(e.get("area", "general"), []).append(e)
    lines.append("## Areas")
    for a, items in sorted(areas.items(), key=lambda kv: -len(kv[1])):
        authors = sorted({i["author"] for i in items})
        lines.append(f"- **{a}**: {len(items)} entries, by {', '.join(authors)}")
    lines += ["", "## Recent (newest first)"]
    for e in es[:25]:
        lines.append(f"- `{e['id']}` {e.get('date','')} · **{e['author']}** ({e['tool']}) · {e.get('area','')} · {e['title']}")
    fmap: dict[str, set] = {}
    for e in es:
        for f in e.get("files", []):
            fmap.setdefault(f, set()).add(e["author"])
    if fmap:
        lines += ["", "## Files by who touched them"]
        for f, authors in sorted(fmap.items())[:120]:
            lines.append(f"- `{f}`: {', '.join(sorted(authors))}")
    eps: dict[str, set] = {}
    for e in es:
        for x in e.get("endpoints", []):
            eps.setdefault(x, set()).add(e["author"])
    if eps:
        lines += ["", "## Endpoints mentioned"]
        for x, authors in sorted(eps.items())[:80]:
            lines.append(f"- `{x}`: {', '.join(sorted(authors))}")
    return "\n".join(lines) + "\n"


def briefing(entries: list[dict], me: str | None, limit: int = 6, max_chars: int = 1800) -> str:
    """Short text injected at session start: what teammates did lately."""
    others = [e for e in entries if e.get("author") != me] or entries
    others = sorted(others, key=lambda e: (e.get("date", ""), e.get("id", "")), reverse=True)[:limit]
    if not others:
        return ""
    out = ["Team brain (gonjineh): recent work by your teammates in this project. Search before you assume something is missing: `gonjineh search \"<words>\"` or MCP tool search_memory."]
    for e in others:
        bits = f"- {e['date']} {e['author']} [{e['area']}] {e['title']}"
        if e.get("files"):
            bits += " (files: " + ", ".join(e["files"][:3]) + ")"
        if e.get("endpoints"):
            bits += " (api: " + ", ".join(e["endpoints"][:3]) + ")"
        out.append(bits)
    txt = "\n".join(out)
    return txt if len(txt) <= max_chars else txt[: max_chars - 1] + "…"
