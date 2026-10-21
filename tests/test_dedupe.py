from dedupe import _is_public_url, normalize_title, normalize_url, url_id


def test_normalize_url_strips_tracking_www_fragment_and_trailing_slash():
    assert (
        normalize_url("http://WWW.Example.com/Story/?utm_source=x&id=7&fbclid=abc#top")
        == "https://example.com/Story?id=7"
    )


def test_normalize_url_keeps_root_path():
    assert normalize_url("https://example.com") == "https://example.com/"


def test_url_variants_share_an_id():
    a = url_id(normalize_url("https://www.example.com/a/?utm_medium=email"))
    b = url_id(normalize_url("http://example.com/a"))
    assert a == b and len(a) == 16


def test_normalize_title_ignores_case_punctuation_and_spacing():
    assert normalize_title("  AI Ads:  The   NEW Normal? ") == normalize_title("ai ads the new normal")


def test_is_public_url_rejects_internal_targets():
    for url in (
        "http://127.0.0.1/",
        "http://169.254.169.254/latest/meta-data",
        "http://10.0.0.5/admin",
        "ftp://93.184.216.34/",
        "file:///etc/passwd",
    ):
        assert not _is_public_url(url), url


def test_is_public_url_accepts_public_ip():
    assert _is_public_url("https://93.184.216.34/")
