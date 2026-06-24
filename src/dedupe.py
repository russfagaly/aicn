"""URL/title normalization and dedup-key helpers.

Dedup key rule (from aicn_data_contract.md): id = hash of the normalized URL.
Normalize before hashing: lowercase scheme/host, strip www., strip tracking
params (utm_*, fbclid, gclid, ...) and fragments, drop trailing slashes, and
prefer <link rel="canonical"> when present. Also normalize the title to catch
cross-outlet syndication.
"""

import concurrent.futures
import hashlib
import re
import urllib.parse
import urllib.request

_TRACKING_PREFIXES = ("utm_",)
_TRACKING_EXACT = {"fbclid", "gclid", "mc_cid", "mc_eid", "igshid", "ref", "ref_src"}

_CANONICAL_RE = re.compile(
    r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)["\']', re.I
)


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


def _fetch_canonical(url: str, timeout: float = 5.0):
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0 (compatible; AICN-dry-run/1.0)"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            html = resp.read(200_000).decode("utf-8", errors="ignore")
        m = _CANONICAL_RE.search(html)
        if m:
            return url, m.group(1)
    except Exception:
        pass
    return url, None


def fetch_canonicals(urls, max_workers: int = 12, timeout: float = 5.0) -> dict:
    """Best-effort canonical-URL lookup for a list of URLs. Returns {url: canonical_or_None}."""
    results = {}
    unique = list(dict.fromkeys(urls))
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [pool.submit(_fetch_canonical, u, timeout) for u in unique]
        for fut in concurrent.futures.as_completed(futures):
            url, canonical = fut.result()
            results[url] = canonical
    return results
