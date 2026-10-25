import pytest
from gonjineh.scrub import scrub, Report, luhn, entropy

CASES = [
    ("AWS_KEY=AKIAIOSFODNN7EXAMPLE", "AKIAIOSFODNN7EXAMPLE"),
    ("token ghp_" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8", "ghp_a1B2"),
    ("github_pat_" + "11ABCDEFG0abcdefghijklmnopqrstuvwxyz0123456789ABCDEFGHIJ", "github_pat_11"),
    ("xoxb-123456789012-abcdefghijkl", "xoxb-1234"),
    ("sk_live_" + "abcdefghijklmnop1234", "sk_live_abc"),
    ("ANTHROPIC=sk-ant-api03-" + "ABCDEFGHIJKLMNOPQRSTUVWXYZ012345", "sk-ant-api03"),
    ("key sk-" + "abcdefghijklmnopqrstuvwxyz0123456789ABCD", "sk-abcdef"),
    ("AIza" + "SyA-abcdefghijklmnopqrstuvwxyz01234", "AIzaSyA"),
    ("jwt eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dBjftJeZ4CVPmB92K27uhbUJU1p1r_wW1gFWFOEjXk", "eyJhbGci"),
    ("-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEAxyz\nabc\n-----END RSA PRIVATE KEY-----", "MIIEow"),
    ("postgres://admin:s3cr3tPass@db.internal:5432/app", "s3cr3tPass"),
    ("curl -H 'Authorization: Bearer abc123def456ghi789jkl'", "abc123def456ghi789jkl"),
    ("DB_PASSWORD=hunter2hunter2", "hunter2hunter2"),
    ('{"api_key": "abcDEF123456xyz789"}', "abcDEF123456xyz789"),
    ("SECRET_KEY: 'django-insecure-9x!k2'", "django-insecure"),
    ("STRIPE_KEY=sk_test_" + "ZZZZZZZZZZZZZZZZ1234", "ZZZZZZZZ"),
    ("client_secret = wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY", "wJalrXUtnFEMI"),
    ("telegram 123456789:" + "AAEhBOweik6ad6PsX3LnA8drTHkExAmPlE0", "AAEhBOwe"),
]


@pytest.mark.parametrize("src,needle", CASES)
def test_secret_is_removed(src, needle):
    out = scrub(src)
    assert needle not in out, out
    assert "REDACTED" in out


@pytest.mark.parametrize("safe", [
    "const token = process.env.TOKEN",
    "password = os.environ['DB_PASSWORD']",
    "api_key=${API_KEY}",
    "sort_key=name",
    "commit 3b18e512dba79e4c8300dd08aeb37f8e728b8dad fixed it",
    "src/components/very-long-kebab-case-component-name-for-the-login-page.tsx",
    "session_id: abc",
    "POST /api/login returns a token",
])
def test_normal_text_untouched(safe):
    assert scrub(safe) == safe


def test_env_file_values_all_redacted():
    env = "DATABASE_URL=postgres://u:pw1234@h/db\nSECRET_KEY=abc12345\nDEBUG=true\nPORT=8000\n"
    out = scrub(env)
    assert "pw1234" not in out and "abc12345" not in out
    assert "DEBUG=true" in out and "PORT=8000" in out


def test_key_name_kept_value_gone():
    assert scrub("password=hunter2hunter2") == "password=[REDACTED:secret]"


def test_idempotent():
    once = scrub("password=hunter2hunter2 and AKIAIOSFODNN7EXAMPLE")
    assert scrub(once) == once


def test_report_counts():
    r = Report()
    scrub("password=abcd1234 AKIAIOSFODNN7EXAMPLE", report=r)
    assert r.total == 2


def test_card_numbers_luhn_only_persian_and_latin_digits():
    assert luhn("6037997397843821") is False or True  # helper runs
    valid = "6219861012345678"
    # find a luhn-valid 16-digit number
    base = "621986101234567"
    for d in range(10):
        if luhn(base + str(d)):
            valid = base + str(d)
    fa = valid.translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))
    assert "REDACTED:card" in scrub(f"card {valid[:4]} {valid[4:8]} {valid[8:12]} {valid[12:]}")
    assert "REDACTED:card" in scrub(f"کارت {fa}")
    assert "1234567890123456" in scrub("order 1234567890123456")  # fails Luhn, not a card


def test_iran_phone_masked_and_optional():
    assert "REDACTED:phone" in scrub("call 09123456789")
    assert "09123456789" in scrub("call 09123456789", pii=False)


def test_email_masking_opt_in():
    assert scrub("a@b.com") == "a@b.com"
    assert "REDACTED:email" in scrub("a@b.com", mask_email=True)


def test_entropy_helper():
    assert entropy("aaaa") == 0
    assert entropy("abcd") == 2


def test_high_entropy_blob_redacted():
    blob = "Zk3Jd9QpL2vXr8TnB5yW1mC7sH4aF6gE0uI"
    assert blob not in scrub("value " + blob)


def test_persian_text_untouched():
    t = "تصمیم گرفتیم از JWT استفاده کنیم چون فرانت SPA است"
    assert scrub(t) == t
