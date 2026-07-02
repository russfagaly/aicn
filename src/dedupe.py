"""URL/title normalization and dedup-key helpers.

Dedup key rule (from aicn_data_contract.md): id = hash of the normalized URL.
Normalize before hashing: lowercase scheme/host, strip www., strip tracking
params (utm_*, fbclid, gclid, ...) and fragments, drop trailing slashes, and
prefer <link rel="canonical"> when present. Also normalize the title to catch
cross-outlet syndication.
"""

import concurrent.futures
import hashlib
import ipaddress
import re
import socket
import urllib.parse
import urllib.request

_TRACKING_PREFIXES = ("utm_",)
_TRACKING_EXACT = {"fbclid", "gclid", "mc_cid", "mc_eid", "igshid", "ref", "ref_src"}

_CANONICAL_RE = re.compile(
    r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)["\']', re.I
)
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
_META_DESC_RE = re.compile(
    r'<meta[^>]+(?:name|property)=["\'](?:description|og:description)["\'][^>]+content=["\']([^"\']*)["\']',
    re.I,
)
_WHITESPACE_RE = re.compile(r"\s+")


def normalize_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url.strip())
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    query_pairs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    kept = [
        (k, v)
        for k, v in query_pairs
        if not k.lower().startswith(_TRACKING_PREFIXES) and k.lower() not in _TRACKING_EXACT
    ]
    query = urllib.parse.urlencode(kept)
    path = parsed.path.rstrip("/") or "/"
    return urllib.parse.urlunsplit(("https", host, path, query, ""))


def url_id(normalized_url: str) -> str:
    return hashlib.sha1(normalized_url.encode("utf-8")).hexdigest()[:16]


def normalize_title(title: str) -> str:
    t = title.lower()
    t = re.sub(r"[^a-z0-9\s]", "", t)
    return re.sub(r"\s+", " ", t).strip()


def _clean_text(raw: str) -> str:
    text = re.sub(r"&amp;", "&", raw)
    text = re.sub(r"&#39;|&apos;", "'", text)
    text = re.sub(r"&quot;", '"', text)
    text = _WHITESPACE_RE.sub(" ", text).strip()
    return text


def _is_public_url(url: str) -> bool:
    """Reject anything but http(s) pointing at a public IP.

    These URLs come from third-party feeds and search results, so treat them as
    untrusted: block non-http(s) schemes and any host that resolves to a
    loopback/private/link-local/reserved address (SSRF guard — e.g. the cloud
    metadata endpoint at 169.254.169.254 or internal services).
    """
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in ("http", "https"):
        return False
    host = parts.hostname
    if not host:
        return False
    try:
        infos = socket.getaddrinfo(host, parts.port or None, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            return False
    return True


class _NoInternalRedirect(urllib.request.HTTPRedirectHandler):
    """Re-validate every redirect hop so a public URL can't bounce to an internal one."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not _is_public_url(newurl):
            return None
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_opener = urllib.request.build_opener(_NoInternalRedirect())


def _fetch_page_meta(url: str, timeout: float = 5.0):
    """Best-effort fetch of a page's canonical URL, <title>, and meta description.

    Grounding the curator in the real page title/description (not just the
    bare title a feed or search result gave us) is what lets it name specific
    people/orgs instead of writing around them vaguely.
    """
    meta = {"canonical": None, "page_title": None, "page_description": None}
    if not _is_public_url(url):
        return url, meta
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0 (compatible; AICN-bot/1.0)"}
        )
        with _opener.open(req, timeout=timeout) as resp:
            html = resp.read(200_000).decode("utf-8", errors="ignore")
        m = _CANONICAL_RE.search(html)
        if m:
            meta["canonical"] = m.group(1)
        m = _TITLE_RE.search(html)
        if m:
            meta["page_title"] = _clean_text(m.group(1))[:200]
        m = _META_DESC_RE.search(html)
        if m:
            meta["page_description"] = _clean_text(m.group(1))[:400]
    except Exception:
        pass
    return url, meta


def fetch_page_metas(urls, max_workers: int = 12, timeout: float = 5.0) -> dict:
    """Best-effort per-URL page metadata. Returns {url: {canonical, page_title, page_description}}."""
    results = {}
    unique = list(dict.fromkeys(urls))
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [pool.submit(_fetch_page_meta, u, timeout) for u in unique]
        for fut in concurrent.futures.as_completed(futures):
            url, meta = fut.result()
            results[url] = meta
    return results
