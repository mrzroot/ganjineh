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


def _e(i, title, **kw):
    e = {"id": i, "title": title, "author": "a", "tool": "t", "date": "2026-01-01", "area": "backend", "areas": ["backend"], "project": "p"}
    e.update(kw)
    return e


def test_search_ranks_title_over_body():
    es = [_e("1", "payment webhook", outcome="x"), _e("2", "refactor", outcome="touches payment webhook once")]
    assert store.search(es, "payment webhook")[0]["id"] == "1"


def test_search_persian_variants_match():
    es = [_e("1", "ورود کاربر با JWT", decisions=["تصمیم گرفتیم از توکن استفاده کنیم"])]
    assert store.search(es, "كاربر")  # Arabic kaf
    assert store.search(es, "ورود jwt")


def test_search_prefix_expansion():
    es = [_e("1", "authentication middleware")]
    assert store.search(es, "auth")


def test_search_area_filter_and_empty():
    es = [_e("1", "login", area="backend", areas=["backend"]), _e("2", "login form", area="frontend", areas=["frontend"])]
    assert [h["id"] for h in store.search(es, "login", area="frontend")] == ["2"]
    assert store.search(es, "zzzz") == []
    assert store.search([], "x") == []


def test_who_knows_by_file_and_endpoint():
    es = [_e("1", "t", author="alice", files=["src/api/users.py"]), _e("2", "t", author="bob", endpoints=["GET /api/users"]),
          _e("3", "t", author="alice", files=["src/api/users.py"])]
    w = store.who_knows(es, "api/users")
    assert w[0]["author"] == "alice" and w[0]["entries"] == 2 and {x["author"] for x in w} == {"alice", "bob"}


def test_render_parse_roundtrip():
    e = _e("abc", "Build login", author="alice", tool="claude-code", session="s", files=["a.py"], endpoints=["POST /x"], decisions=["use jwt because spa"],
           outcome="done", asks=["do it"], todos=["later maybe todo"], gotchas=[], commands=["pytest"], tags=["auth"], branch="main", turns=2)
    p = store.parse(store.render(e))
    for k in ("id", "title", "author", "files", "endpoints", "decisions", "asks", "outcome", "tags", "todos"):
        assert p[k] == e[k], k


def test_index_lists_files_and_authors():
    es = [_e("1", "t", author="alice", files=["a.py"], endpoints=["GET /x"])]
    txt = store.build_index(es, "p")
    assert "`a.py`: alice" in txt and "GET /x" in txt


def test_briefing_prefers_teammates_and_caps():
    es = [_e(str(i), f"task {i}", author="bob" if i % 2 else "me", date=f"2026-01-{i+1:02d}") for i in range(10)]
    b = store.briefing(es, "me", limit=3)
    assert "me [" not in b and len(b) <= 1800
    assert store.briefing([], "me") == ""
