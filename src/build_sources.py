"""Build sources.html from the gathering config.

sources.html used to be hand-maintained, and it drifted from what the pipeline
actually collects — twice in two months. By the time this was written it listed
8 of 10 feeds, named 2 of 10 site-scoped search targets, and still claimed
coverage of AP and Politico, both dropped on 2026-07-21 for blocking the
crawler. A page whose entire purpose is methodology transparency cannot be the
one artifact that isn't derived from the machinery it describes.

Generating it from sources.yaml + site_targets.yaml + watchlist.yaml makes that
drift structurally impossible: accepting a proposal updates the page on the next
run. Rendered on every pipeline execution, the same as library.html.
"""

import html
import os

import yaml

from build_library import _POSTHOG

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Shown under each watchlist entity. The config's `kind` values are terse and
# internal; these are what a reader should see.
KIND_LABELS = {
    "vendor": "Vendor",
    "regulator": "Regulator",
    "legislation": "Legislation",
    "person": "Person",
    "org_no_feed": "Organization (no feed)",
}


def esc(s):
    return html.escape(str(s or ""), quote=True)


def _load(root, name):
    with open(os.path.join(root, name)) as f:
        return yaml.safe_load(f) or {}


def _section_head(a, title, count):
    a('      <section style="margin-top:32px;">')
    a('        <div style="display:flex; align-items:center; gap:12px; margin:0 0 16px;">')
    a(f'          <h2 style="font-family:\'Source Serif 4\',serif; font-weight:600; font-size:17px; color:#1d2330; margin:0; white-space:nowrap;">{esc(title)}</h2>')
    a(f'          <span style="font-family:\'IBM Plex Mono\',monospace; font-size:11px; color:#9aa1ab;">{count}</span>')
    a('          <div style="flex:1; height:1px; background:#e3e6ea;"></div>')
    a('        </div>')


def _grid_open(a):
    a('        <ul style="list-style:none; margin:0; padding:0; display:grid; grid-template-columns:repeat(auto-fit, minmax(240px, 1fr)); gap:0 32px;">')


def _item(a, label, sublabel, href=None):
    a('          <li style="padding:14px 0; border-bottom:1px solid #e7eaee;">')
    if href:
        a(f'            <a href="{esc(href)}" target="_blank" rel="noopener" style="font-size:14.5px; font-weight:600; text-decoration:none; color:#1d2330; display:block;">{esc(label)}</a>')
    else:
        a(f'            <span style="font-size:14.5px; font-weight:600; color:#1d2330; display:block;">{esc(label)}</span>')
    a(f'            <span style="font-size:12px; color:#9aa1ab;">{esc(sublabel)}</span>')
    a('          </li>')


def build_sources_html(root: str = ROOT) -> str:
    feeds = _load(root, "sources.yaml").get("feeds", []) or []
    targets = _load(root, "site_targets.yaml").get("targets", []) or []
    entities = _load(root, "watchlist.yaml").get("entities", []) or []

    out = []
    a = out.append

    a('<!DOCTYPE html>')
    a('<html lang="en">')
    a('<head>')
    a('  <meta charset="utf-8">')
    a('  <meta name="viewport" content="width=device-width, initial-scale=1">')
    a('  <title>Sources — AICN</title>')
    a('  <link rel="preconnect" href="https://fonts.googleapis.com">')
    a('  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>')
    a('  <link href="https://fonts.googleapis.com/css2?family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,500;0,8..60,600;0,8..60,700&family=Public+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">')
    a('  <style>')
    a('    * { box-sizing: border-box; }')
    a('    body { margin: 0; }')
    a('    a { color: #2b4a8b; }')
    a('    @media (max-width: 640px) {')
    a('      header > div { padding: 20px 16px 16px !important; gap: 16px !important; }')
    a('      header > div > div { max-width: 100% !important; }')
    a('      main { padding: 24px 16px 48px !important; }')
    a('      footer > div { padding: 20px 16px 28px !important; }')
    a('    }')
    a('  </style>')
    a('  <script>')
    a('    ' + _POSTHOG)
    a("    posthog.init('phc_qZHPCa5BvVBCziaXPvLcvUNcaPb6o59bLCURxSmgy9Wy', { api_host: 'https://us.i.posthog.com', person_profiles: 'identified_only' });")
    a('  </script>')
    a('</head>')
    a('<body>')
    a('  <div style="min-height:100vh; background:#eef0f3; font-family:\'Public Sans\',sans-serif; color:#2a2f3a;">')

    a('    <header style="background:#fff; border-bottom:1px solid #e3e6ea;">')
    a('      <div style="max-width:880px; margin:0 auto; padding:28px 28px 24px; display:flex; justify-content:space-between; align-items:flex-end; gap:24px; flex-wrap:wrap;">')
    a('        <div>')
    a('          <div style="display:flex; align-items:baseline; gap:12px;">')
    a('            <a href="index.html" style="font-family:\'Source Serif 4\',serif; font-weight:700; font-size:30px; letter-spacing:-0.01em; color:#1d2330; text-decoration:none;">AICN</a>')
    a('            <span style="font-size:13px; letter-spacing:0.16em; text-transform:uppercase; color:#2b4a8b; font-weight:600;">AI Campaign News</span>')
    a('          </div>')
    a('          <p style="margin:8px 0 0; font-size:14.5px; color:#6b7280; max-width:52ch; line-height:1.5;">Tracking AI use in political campaigns, elections, and issue advocacy.</p>')
    a('        </div>')
    a('        <nav style="display:flex; gap:10px 14px; flex-wrap:wrap; align-items:center;">')
    a('          <a href="index.html" style="font-size:13px; color:#6b7280; text-decoration:none;">Home</a>')
    a('          <a href="library.html" style="font-size:13px; color:#6b7280; text-decoration:none;">Library</a>')
    a('          <a href="sources.html" style="font-size:13px; color:#2b4a8b; font-weight:600; text-decoration:none; border-bottom:2px solid #2b4a8b; padding-bottom:1px;">Sources</a>')
    a('          <a href="proposals.html" style="font-size:13px; color:#6b7280; text-decoration:none;">Pipeline</a>')
    a('          <a href="feed.xml" style="font-size:12.5px; color:#2b4a8b; text-decoration:none; border:1px solid #cdd7ea; padding:4px 11px; border-radius:999px;">RSS</a>')
    a('        </nav>')
    a('      </div>')
    a('    </header>')
    a('')

    a('    <main style="max-width:880px; margin:0 auto; padding:32px 28px 64px;">')
    a('      <div style="margin-bottom:24px;">')
    a('        <h1 style="font-family:\'Source Serif 4\',serif; font-weight:700; font-size:26px; color:#1d2330; margin:0 0 8px;">Sources</h1>')
    a('        <p style="margin:0; font-size:14px; color:#6b7280; line-height:1.6; max-width:60ch;">')
    a('          AICN gathers candidates from three layers: curated RSS/Atom feeds, site-scoped')
    a('          searches of outlets that publish no usable feed, and an entity watchlist of')
    a('          vendors, regulators, and legislation tracked by name. A broad web search pass')
    a('          runs alongside them, so items can surface from outside this list. Everything')
    a('          gathered is filtered for relevance before publishing.')
    a('        </p>')
    a('        <p style="margin:12px 0 0; font-size:13px; color:#9aa1ab; line-height:1.6; max-width:60ch;">')
    a('          This page is generated from the pipeline\'s own configuration on every run, so')
    a('          it always reflects what is actually being gathered.')
    a('        </p>')
    a('      </div>')

    _section_head(a, "Curated RSS/Atom feeds", len(feeds))
    _grid_open(a)
    for f in feeds:
        _item(a, f.get("name", ""), f.get("description", ""), href=f.get("url"))
    a('        </ul>')
    a('      </section>')

    _section_head(a, "Site-scoped search targets", len(targets))
    a('        <p style="font-size:13px; color:#6b7280; line-height:1.6; margin:0 0 8px; max-width:60ch;">')
    a('          Outlets searched directly each run because they publish no usable RSS feed, or')
    a('          publish far more than AI-in-campaigns coverage alone.')
    a('        </p>')
    _grid_open(a)
    for t in targets:
        _item(a, t.get("name", ""), t.get("description") or t.get("domain", ""))
    a('        </ul>')
    a('      </section>')

    _section_head(a, "Entity watchlist", len(entities))
    a('        <p style="font-size:13px; color:#6b7280; line-height:1.6; margin:0 0 8px; max-width:60ch;">')
    a('          Named vendors, regulators, and legislation searched by name each run, so')
    a('          coverage does not depend on any single outlet reporting on them.')
    a('        </p>')
    _grid_open(a)
    for e in entities:
        _item(a, e.get("name", ""), KIND_LABELS.get(e.get("kind"), e.get("kind", "")))
    a('        </ul>')
    a('      </section>')
    a('    </main>')
    a('')

    a('    <footer style="background:#fff; border-top:1px solid #e3e6ea;">')
    a('      <div style="max-width:880px; margin:0 auto; padding:24px 28px 36px; font-size:12.5px; color:#8a909b; line-height:1.7;">')
    a('        <p style="margin:0 0 6px;">AICN is a static digest compiled by an automated daily research pipeline that scans news, regulatory, and vendor sources for AI use in political campaigns and elections, then summarizes each item in a neutral, third-party voice.</p>')
    a('        <p style="margin:0;"><a href="index.html" style="color:#2b4a8b; text-decoration:none;">Home</a> · <a href="library.html" style="color:#2b4a8b; text-decoration:none;">Library</a> · <a href="proposals.html" style="color:#2b4a8b; text-decoration:none;">Pipeline</a> · <a href="feed.xml" style="color:#2b4a8b; text-decoration:none;">RSS feed</a>. Vendor-reported figures are labeled as such and are not independently verified.</p>')
    a('      </div>')
    a('    </footer>')
    a('  </div>')
    a('</body>')
    a('</html>')

    path = os.path.join(root, "sources.html")
    with open(path, "w") as f:
        f.write("\n".join(out) + "\n")
    return path


if __name__ == "__main__":
    print(build_sources_html())
