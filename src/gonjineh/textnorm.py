"""Persian-aware text normalisation and tokenisation (stdlib only).

The same rules are ported 1:1 to JavaScript for the landing-page demo.
"""
from __future__ import annotations
import re

_MAP = {
    "\u064a": "\u06cc",  # Arabic yeh -> Persian yeh
    "\u0649": "\u06cc",  # alef maksura -> Persian yeh
    "\u0643": "\u06a9",  # Arabic kaf -> Persian keheh
    "\u0629": "\u0647",  # teh marbuta -> heh
    "\u06c0": "\u0647",  # heh with yeh above -> heh
    "\u200c": " ",        # ZWNJ -> space (so "می‌شود" and "می شود" match)
    "\u200d": "",         # ZWJ
    "\u200f": "", "\u200e": "", "\u0640": "",  # RLM, LRM, tatweel
}
for i, ch in enumerate("۰۱۲۳۴۵۶۷۸۹"):
    _MAP[ch] = str(i)
for i, ch in enumerate("٠١٢٣٤٥٦٧٨٩"):
    _MAP[ch] = str(i)
_TRANS = {ord(k): v for k, v in _MAP.items()}
_TASHKEEL = re.compile("[\u064b-\u065f\u0670]")
_SPLIT_CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_TOKEN = re.compile(r"[0-9a-z\u0600-\u06ff]+")

STOP = frozenset("""the a an and or of to in on for with is are was were be been it this that as at by from not no
را و در به از که این آن با برای یک است بود شد می های ها تا هم یا اگر
""".split())


def normalize(text: str) -> str:
    text = _TASHKEEL.sub("", text.translate(_TRANS))
    return text


def tokenize(text: str) -> list[str]:
    text = _SPLIT_CAMEL.sub(" ", text.translate({ord("_"): " ", ord("-"): " ", ord("/"): " ", ord("."): " "}))
    text = normalize(text).lower()
    return [t for t in _TOKEN.findall(text) if t not in STOP and len(t) > 0 and not (len(t) == 1 and t.isascii())]
