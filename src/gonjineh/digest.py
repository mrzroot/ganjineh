"""Heuristic, LLM-free digest of a Session into a compact memory entry."""
from __future__ import annotations
import fnmatch
import hashlib
import re
from datetime import datetime, timezone

from .scrub import Report, scrub
from .transcripts import Session

DEFAULT_AREAS = [
    ("frontend", ["*.tsx", "*.jsx", "*.vue", "*.svelte", "*.css", "*.scss", "*.html", "*/components/*", "*/pages/*", "*/public/*", "frontend/*", "web/*", "client/*", "ui/*", "app/*"]),
    ("backend", ["*.py", "*.go", "*.rs", "*.java", "*.php", "*.rb", "*.sql", "*/api/*", "*/routes/*", "*/models/*", "*/migrations/*", "backend/*", "server/*", "api/*", "services/*"]),
    ("infra", ["Dockerfile*", "docker-compose*", "*.tf", ".github/*", "k8s/*", "deploy/*", "infra/*", "*.yml", "*.yaml", "nginx*"]),
    ("docs", ["*.md", "docs/*"]),
]
DECISION = re.compile(r"\b(decided|chose|choosing|we(?:'ll| will) use|i(?:'ll| will) use|instead of|switched to|going with|opted for|rather than|the reason|because)\b|تصمیم|انتخاب کرد|به جای|استفاده می[‌ ]?کنیم|به این دلیل|چون", re.I)
TODO = re.compile(r"\b(TODO|FIXME|still need|not yet|next step|follow[- ]up|left to do|remaining)\b|باقی[‌ ]?مانده|هنوز|بعداً|مرحله بعد", re.I)
GOTCHA = re.compile(r"\b(gotcha|careful|caveat|watch out|beware|warning|note that|breaking|workaround|must not|never)\b|حواست|دقت|نکته|مراقب", re.I)
ENDPOINT = [
    re.compile(r"\b(GET|POST|PUT|PATCH|DELETE)\s+(/[\w\-./:{}<>\[\]]*)"),
    re.compile(r"""@(?:\w+)\.(get|post|put|patch|delete)\(\s*["'](/[^"']*)"""),
    re.compile(r"""\b(?:app|router)\.(get|post|put|patch|delete)\(\s*["'](/[^"']*)"""),
    re.compile(r"""\b(?:fetch|axios\.(get|post|put|patch|delete))\(\s*[`"'](/[\w\-./:{}$]*)"""),
]
SHELL_WRITE = [re.compile(r"(?<![0-9&<>])>>?\s*(['\"]?)([\w./\-~]+\.\w+|[\w./\-]+/[\w./\-]+)\1"),
               re.compile(r"\btee\s+(?:-a\s+)?(['\"]?)([\w./\-]+)\1"),
               re.compile(r"\bsed\s+-i\S*\s+(?:-e\s+)?(?:'[^']*'|\"[^\"]*\")\s+(['\"]?)([\w./\-]+)\1"),
               re.compile(r"\b(?:touch|mkdir -p)\s+(['\"]?)([\w./\-]+\.\w+)\1")]
SENT = re.compile(r"(?<=[.!?؟۔\n])\s+")
NOTABLE_CMD = re.compile(r"^\s*(git (?!status|diff|log|add)|npm (?:i|install|run|test)|pnpm|yarn|pip|pytest|python -m|docker|make|cargo|go (?:test|build)|alembic|prisma|migrate|curl|kubectl|terraform)\b")


def _first(text: str, n: int) -> str:
    t = " ".join(text.split())
    return t if len(t) <= n else t[: n - 1].rstrip() + "…"


def _rel(path: str, cwd: str) -> str:
    path = path.replace("\\", "/")
    c = cwd.replace("\\", "/").rstrip("/")
    if c and path.startswith(c + "/"):
        path = path[len(c) + 1:]
    return path.lstrip("./") if path.startswith("./") else path


def load_ignore(text: str) -> list[str]:
    return [l.strip() for l in text.splitlines() if l.strip() and not l.strip().startswith("#")]


def ignored(path: str, patterns: list[str]) -> bool:
    p = path.lstrip("/")
    return any(fnmatch.fnmatch(p, pat) or fnmatch.fnmatch("/" + p, pat) or fnmatch.fnmatch(p.split("/")[-1], pat) for pat in patterns)


def infer_areas(files: list[str], rules=None, default: str = "general") -> list[str]:
    rules = rules or DEFAULT_AREAS
    counts: dict[str, int] = {}
    for f in files:
        for area, globs in rules:
            if any(fnmatch.fnmatch(f, g) or fnmatch.fnmatch("/" + f, g) or fnmatch.fnmatch(f, "*/" + g) for g in globs):
                counts[area] = counts.get(area, 0) + 1
                break
    if not counts:
        return [default]
    return [a for a, _ in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]


def sentences(text: str):
    for part in SENT.split(text):
        part = " ".join(part.split())
        if part:
            yield part


def build_entry(s: Session, *, author: str, project: str, area_rules=None, default_area="general",
                ignore_patterns=None, detail="normal", min_signal=True, pii=True, mask_email=False) -> tuple[dict, Report] | None:
    """Return (entry, scrub report) or None if the session should not be stored."""
    ignore_patterns = ignore_patterns or []
    users = [t for r, t in s.messages if r == "user"]
    assistants = [t for r, t in s.messages if r == "assistant"]
    if not users:
        return None
    joined_user = "\n".join(users)
    if re.search(r"(#private\b|gonjineh:off|#نهان\b)", joined_user):
        return None
    files, seen = [], set()
    for name, inp in s.tool_calls:
        fp = inp.get("file_path") or inp.get("path") or inp.get("notebook_path")
        if name in ("Edit", "Write", "MultiEdit", "NotebookEdit", "apply_patch") and fp:
            fp = _rel(str(fp), s.cwd)
            if fp not in seen:
                seen.add(fp)
                files.append(fp)
    for name, inp in s.tool_calls:
        c = inp.get("command")
        if name == "Bash" and isinstance(c, str):
            for rx in SHELL_WRITE:
                for m in rx.finditer(c):
                    fp = _rel(m.group(2), s.cwd)
                    if fp.startswith(("/dev/", "/tmp/", "/proc/")) or fp in seen:
                        continue
                    seen.add(fp)
                    files.append(fp)
    all_files = files
    files = [f for f in files if not ignored(f, ignore_patterns)]
    if all_files and not files:
        return None  # everything touched is ignored
    commands = []
    for name, inp in s.tool_calls:
        c = inp.get("command")
        if name == "Bash" and isinstance(c, str) and NOTABLE_CMD.search(c):
            c = _first(c.splitlines()[0], 140)
            if c not in commands:
                commands.append(c)
    if min_signal and not files and len(assistants) < 1:
        return None
    corpus = assistants + [str(i.get("content", "")) + str(i.get("new_string", "")) for _, i in s.tool_calls if isinstance(i, dict)]
    endpoints = []
    for text in assistants + [t for t in corpus if t]:
        for rx in ENDPOINT:
            for m in rx.finditer(text):
                g = [x for x in m.groups() if x]
                if len(g) >= 2:
                    verb, path = g[-2].upper(), g[-1]
                else:
                    verb, path = "", g[-1]
                path = path.rstrip(".,;:)'\"`")
                e = (verb + " " + path).strip()
                if e not in endpoints and len(path) > 1:
                    endpoints.append(e)
    decisions, todos, gotchas = [], [], []
    for text in assistants:
        for sent in sentences(text):
            if not 25 <= len(sent) <= 260:
                continue
            if DECISION.search(sent) and sent not in decisions:
                decisions.append(sent)
            if TODO.search(sent) and sent not in todos:
                todos.append(sent)
            if GOTCHA.search(sent) and sent not in gotchas:
                gotchas.append(sent)
    n_user, n_len = (8, 280) if detail == "normal" else (3, 160)
    asks = [_first(u, n_len) for u in users[:n_user]]
    outcome = _first(assistants[-1], 700 if detail == "normal" else 300) if assistants else ""
    title = _first(users[0].splitlines()[0], 90)
    areas = infer_areas(files, area_rules, default_area)
    when = s.ended or s.started or datetime.now(timezone.utc).isoformat()
    date = when[:10] if re.match(r"\d{4}-\d{2}-\d{2}", when) else datetime.now(timezone.utc).strftime("%Y-%m-%d")
    entry = {
        "id": hashlib.sha1(f"{s.tool}:{s.session_id}".encode()).hexdigest()[:10],
        "title": title,
        "author": author,
        "tool": s.tool,
        "session": s.session_id[:12],
        "date": date,
        "project": project,
        "area": areas[0],
        "areas": areas,
        "branch": s.branch,
        "files": files[:40],
        "endpoints": endpoints[:12],
        "tags": [],
        "asks": asks,
        "outcome": outcome,
        "decisions": decisions[:6],
        "gotchas": gotchas[:5],
        "todos": todos[:6],
        "commands": commands[:8],
        "turns": len(users),
    }
    rep = Report()
    clean = scrub_entry(entry, rep, pii, mask_email)
    return clean, rep


def scrub_entry(entry: dict, rep: Report | None = None, pii: bool = True, mask_email: bool = False) -> dict:
    rep = rep if rep is not None else Report()
    out = {}
    for k, v in entry.items():
        if k in ("id", "author", "tool", "session", "date", "project", "area", "areas", "branch", "turns"):
            out[k] = v
        elif isinstance(v, list):
            out[k] = [scrub(x, pii=pii, mask_email=mask_email, report=rep) if isinstance(x, str) else x for x in v]
        elif isinstance(v, str):
            out[k] = scrub(v, pii=pii, mask_email=mask_email, report=rep)
        else:
            out[k] = v
    return out
