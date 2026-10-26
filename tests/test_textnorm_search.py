"""Persian-aware text normalization (ganjineh.textnorm) and the entry store (ganjineh.store): search ranking,
Persian spelling variants, `who knows`, render/parse round trip, index and briefing.
"""

from ganjineh import store
from ganjineh.textnorm import normalize, tokenize


def test_arabic_yeh_kaf_unified():
    assert normalize("كتاب علي") == normalize("کتاب علی")


def test_digits_unified():
    assert normalize("۱۲۳٤٥") == "12345"


def test_zwnj_equals_space():
    assert tokenize("می‌شود") == tokenize("می شود")


def test_tashkeel_removed():
    assert normalize("مُحَمَّد") == "محمد"


def test_camel_and_snake_split():
    assert tokenize("getUserById user_profile") == ["get", "user", "id", "user", "profile"]
    assert "login" in tokenize("LoginForm") and "form" in tokenize("LoginForm")


def test_path_tokens():
    assert "auth" in tokenize("backend/auth.py")


def make_entry(i, title, **fields):
    """A minimal brain entry with the given id and title; `fields` override or extend the defaults."""
    entry = {
        "id": i,
        "title": title,
        "author": "a",
        "tool": "t",
        "date": "2026-01-01",
        "area": "backend",
        "areas": ["backend"],
        "project": "p",
    }
    entry.update(fields)
    return entry


def test_search_ranks_title_over_body():
    entries = [
        make_entry("1", "payment webhook", outcome="x"),
        make_entry("2", "refactor", outcome="touches payment webhook once"),
    ]
    assert store.search(entries, "payment webhook")[0]["id"] == "1"


def test_search_persian_variants_match():
    entries = [make_entry("1", "ورود کاربر با JWT", decisions=["تصمیم گرفتیم از توکن استفاده کنیم"])]
    assert store.search(entries, "كاربر")  # Arabic kaf
    assert store.search(entries, "ورود jwt")


def test_search_prefix_expansion():
    entries = [make_entry("1", "authentication middleware")]
    assert store.search(entries, "auth")


def test_search_area_filter_and_empty():
    entries = [
        make_entry("1", "login", area="backend", areas=["backend"]),
        make_entry("2", "login form", area="frontend", areas=["frontend"]),
    ]
    assert [h["id"] for h in store.search(entries, "login", area="frontend")] == ["2"]
    assert store.search(entries, "zzzz") == []
    assert store.search([], "x") == []


def test_who_knows_by_file_and_endpoint():
    entries = [
        make_entry("1", "t", author="alice", files=["src/api/users.py"]),
        make_entry("2", "t", author="bob", endpoints=["GET /api/users"]),
        make_entry("3", "t", author="alice", files=["src/api/users.py"]),
    ]
    ranking = store.who_knows(entries, "api/users")
    assert ranking[0]["author"] == "alice" and ranking[0]["entries"] == 2
    assert {row["author"] for row in ranking} == {"alice", "bob"}


def test_render_parse_roundtrip():
    entry = make_entry(
        "abc",
        "Build login",
        author="alice",
        tool="claude-code",
        session="s",
        files=["a.py"],
        endpoints=["POST /x"],
        decisions=["use jwt because spa"],
        outcome="done",
        asks=["do it"],
        todos=["later maybe todo"],
        gotchas=[],
        commands=["pytest"],
        tags=["auth"],
        branch="main",
        turns=2,
    )
    parsed = store.parse(store.render(entry))
    for key in ("id", "title", "author", "files", "endpoints", "decisions", "asks", "outcome", "tags", "todos"):
        assert parsed[key] == entry[key], key


def test_index_lists_files_and_authors():
    entries = [make_entry("1", "t", author="alice", files=["a.py"], endpoints=["GET /x"])]
    index = store.build_index(entries, "p")
    assert "`a.py`: alice" in index and "GET /x" in index


def test_briefing_prefers_teammates_and_caps():
    entries = [
        make_entry(str(i), f"task {i}", author="bob" if i % 2 else "me", date=f"2026-01-{i + 1:02d}") for i in range(10)
    ]
    briefing = store.briefing(entries, "me", limit=3)
    assert "me [" not in briefing and len(briefing) <= 1800
    assert store.briefing([], "me") == ""
