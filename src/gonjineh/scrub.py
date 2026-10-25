"""Secret and PII scrubber. Runs on everything before it is written to the shared brain.

Philosophy: false positives are cheap (a word becomes [REDACTED]), a leaked key is not.
"""
from __future__ import annotations
import math
import re
from dataclasses import dataclass, field

PLACEHOLDER = re.compile(
    r"^(?:\$\{?\w+\}?|\$\(.*\)|<[^>]*>|\[REDACTED[^\]]*\]|\*{3,}|x{4,}|\.{3,}|your[-_ ].*|process\.env\..*|os\.environ.*|"
    r"getenv.*|env\(.*|null|none|nil|true|false|undefined|example.*|changeme|todo|string|str|int|bool|password|secret|token)$",
    re.I,
)
STRONG = re.compile(r"(secret|token|passw(?:or)?d|passwd|pwd|api[_-]?key|apikey|private[_-]?key|access[_-]?key|credential|bearer|signature)", re.I)
WEAK = re.compile(r"(key|auth|cred|salt|dsn|cookie|session)", re.I)

PRIVATE_KEY = re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY(?: BLOCK)?-----.*?(?:-----END [A-Z0-9 ]*PRIVATE KEY(?: BLOCK)?-----|\Z)", re.S)
TOKEN_RULES = [
    ("aws-access-key", re.compile(r"\b(?:AKIA|ASIA|AGPA|AIDA|AROA)[0-9A-Z]{16}\b")),
    ("github-token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,255}|github_pat_[A-Za-z0-9_]{40,255})\b")),
    ("gitlab-token", re.compile(r"\bglpat-[A-Za-z0-9_\-]{20,}\b")),
    ("slack-token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b")),
    ("stripe-key", re.compile(r"\b(?:sk|rk|pk)_(?:live|test)_[A-Za-z0-9]{16,}\b")),
    ("anthropic-key", re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}\b")),
    ("openai-key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_\-]{32,}\b")),
    ("google-api-key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    ("npm-token", re.compile(r"\bnpm_[A-Za-z0-9]{36}\b")),
    ("sendgrid-key", re.compile(r"\bSG\.[A-Za-z0-9_\-]{16,}\.[A-Za-z0-9_\-]{16,}\b")),
    ("twilio-key", re.compile(r"\bSK[0-9a-f]{32}\b")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_\-]{8,}\.eyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{4,}\b")),
    ("telegram-bot-token", re.compile(r"\b\d{8,10}:[A-Za-z0-9_\-]{35}\b")),
]
URL_CREDS = re.compile(r"(\b[a-z][a-z0-9+.\-]*://)([^\s/:@]+):([^\s/@]+)@", re.I)
BEARER = re.compile(r"(?i)\b(Bearer|Basic|Token)\s+([A-Za-z0-9._~+/=\-]{12,})")
ASSIGN = re.compile(
    r"""(?ix)
    (["']?)([A-Za-z0-9_.\-]*(?:secret|token|passw(?:or)?d|passwd|pwd|key|auth|cred|salt|dsn|cookie|session|signature)[A-Za-z0-9_.\-]*)\1
    (\s*(?::|=|=>|:=)\s*)
    (["']?)([^\s"'`,;&)}\]]{4,})
    """
)
CARD = re.compile(r"(?<![0-9۰-۹])(?:[0-9۰-۹]{4}[ \-]?){3}[0-9۰-۹]{4}(?![0-9۰-۹])")
PHONE_IR = re.compile(r"(?<![0-9۰-۹])(?:\+98|0098|0)?[9۹][0-9۰-۹]{9}(?![0-9۰-۹])")
EMAIL = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")
LONG = re.compile(r"(?<![A-Za-z0-9+_=\-])[A-Za-z0-9+_=\-]{32,}(?![A-Za-z0-9+_=\-])")
_FA = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")


@dataclass
class Report:
    counts: dict = field(default_factory=dict)

    def hit(self, kind: str) -> None:
        self.counts[kind] = self.counts.get(kind, 0) + 1

    @property
    def total(self) -> int:
        return sum(self.counts.values())


def entropy(s: str) -> float:
    if not s:
        return 0.0
    freq = {c: s.count(c) for c in set(s)}
    return -sum(n / len(s) * math.log2(n / len(s)) for n in freq.values())


def luhn(digits: str) -> bool:
    total, alt = 0, False
    for ch in reversed(digits):
        d = int(ch)
        if alt:
            d *= 2
            if d > 9:
                d -= 9
        total += d
        alt = not alt
    return total % 10 == 0


def _redact(kind: str) -> str:
    return f"[REDACTED:{kind}]"


def scrub(text: str, *, pii: bool = True, mask_email: bool = False, report: Report | None = None) -> str:
    """Return *text* with secrets (and, if pii, Iranian card/phone numbers) replaced by [REDACTED:kind]."""
    if not text:
        return text
    rep = report if report is not None else Report()

    def sub(rx, kind, s, repl=None):
        def f(m):
            rep.hit(kind)
            return repl(m) if repl else _redact(kind)
        return rx.sub(f, s)

    text = sub(PRIVATE_KEY, "private-key", text)
    for kind, rx in TOKEN_RULES:
        text = sub(rx, kind, text)
    text = sub(URL_CREDS, "url-credentials", text, lambda m: f"{m.group(1)}{m.group(2)}:{_redact('password')}@")
    text = sub(BEARER, "bearer", text, lambda m: f"{m.group(1)} {_redact('token')}")

    def assign(m):
        quote, key, sep, vq, val = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)
        if PLACEHOLDER.match(val) or val.startswith("[REDACTED"):
            return m.group(0)
        strong = bool(STRONG.search(key))
        if not strong:
            mixed = any(c.isdigit() for c in val) and any(c.isalpha() for c in val)
            if not (len(val) >= 12 and mixed and not val.startswith(("http://", "https://", "/", "./"))):
                return m.group(0)
        rep.hit("assigned-secret")
        return f"{quote}{key}{quote}{sep}{vq}{_redact('secret')}"
    text = ASSIGN.sub(assign, text)

    def long(m):
        t = m.group(0)
        if re.fullmatch(r"[0-9a-fA-F]+", t):  # git SHAs, content hashes: not secrets
            return t
        if not (any(c.isdigit() for c in t) and any(c.isalpha() for c in t)):
            return t
        if t.count("-") + t.count("_") > 6 and entropy(t) < 4.4:  # kebab/snake identifiers
            return t
        if entropy(t) >= 4.0:
            rep.hit("high-entropy")
            return _redact("high-entropy")
        return t
    text = LONG.sub(long, text)

    if pii:
        def card(m):
            d = m.group(0).translate(_FA)
            d = re.sub(r"[ \-]", "", d)
            if luhn(d):
                rep.hit("card-number")
                return _redact("card")
            return m.group(0)
        text = CARD.sub(card, text)
        text = sub(PHONE_IR, "phone", text, lambda m: _redact("phone"))
    if mask_email:
        text = sub(EMAIL, "email", text)
    return text


def scrub_obj(o, **kw):
    if isinstance(o, str):
        return scrub(o, **kw)
    if isinstance(o, list):
        return [scrub_obj(x, **kw) for x in o]
    if isinstance(o, dict):
        return {k: scrub_obj(v, **kw) for k, v in o.items()}
    return o
