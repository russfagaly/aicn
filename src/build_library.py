"""Build library.html from data/library.md.

Parses the hand-maintained research library and generates a static HTML page
with theme-tag filtering. Run on every pipeline execution so the page stays
in sync with the file whenever library.md is updated.

Parse contract:
  - Entries start with ## [NNN] Title of Entry
  - Metadata lives in a markdown table: | **Field** | value |
  - Fields extracted: URL, Source, Published, Themes (comma-separated)
  - All other fields are ignored by this script
  - Confidential entries are absent from library.md — no exclusion logic needed
"""

import html
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# PostHog snippet (same key as index.html)
_POSTHOG = (
    "!function(t,e){var o,n,p,r;e.__SV||(window.posthog=e,e._i=[],e.init=function(i,s,a)"
    "{function g(t,e){var o=e.split(\".\");2==o.length&&(t=t[o[0]],e=o[1]),t[e]=function()"
    "{t.push([e].concat(Array.prototype.slice.call(arguments,0)))}}(p=t.createElement(\"script\"))"
    ".type=\"text/javascript\",p.crossOrigin=\"anonymous\",p.async=!0,p.src=s.api_host.replace"
    "(\".i.posthog.com\",\"-assets.i.posthog.com\")+\"/static/array.js\",(r=t.getElementsByTagName"
    "(\"script\")[0]).parentNode.insertBefore(p,r);var u=e;for(void 0!==a?u=e[a]=[]:"
    "a=\"posthog\",u.people=u.people||[],u.toString=function(t){var e=\"posthog\";return\"posthog\""
    "!==a&&(e+=\".\"+a),t||(e+=\" (stub)\"),e},u.people.toString=function(){return u.toString(1)"
    "+\".people (stub)\"},o=\"init bs ws ge fs capture je Di ks register register_once "
    "register_for_session unregister unregister_for_session Ps getFeatureFlag getFeatureFlagPayload "
    "isFeatureEnabled reloadFeatureFlags updateEarlyAccessFeatureEnrollment getEarlyAccessFeatures "
    "on onFeatureFlags onSessionId getSurveys getActiveMatchingSurveys renderSurvey canRenderSurvey "
    "getNextSurveyStep identify setPersonProperties group resetGroups setPersonPropertiesForFlags "
    "resetPersonPropertiesForFlags setGroupPropertiesForFlags resetGroupPropertiesForFlags reset "
    "get_distinct_id getGroups setPersonProperties getPersonData refreshAssociatedFlags get_session_id "
    "get_session_replay_url alias set_config startSessionRecording stopSessionRecording "
    "sessionRecordingStarted captureException loadToolbar get_property getSessionProperty Cs Es "
    "createPersonProfile Is Ss opt_in_capturing opt_out_capturing has_opted_in_capturing "
    "has_opted_out_capturing clear_opt_in_out_capturing Rs debug L Ts getPageViewId "
    "captureTraceFeedback captureTraceMetric\".split(\" \"),n=0;n<o.length;n++)g(u,o[n]);"
    "e._i.push([i,s,a])},e.__SV=1)}(document,window.posthog||[]);"
)


def _field(chunk: str, name: str) -> str:
    m = re.search(
        r'\|\s*\*\*' + re.escape(name) + r'\*\*\s*\|\s*(.+?)\s*\|',
        chunk, re.IGNORECASE
    )
    return m.group(1).strip() if m else ''


def parse_library(md_text: str) -> list:
    entries = []
    chunks = re.split(r'^(?=## \[\d+\])', md_text, flags=re.MULTILINE)
    for chunk in chunks:
        m = re.match(r'^## \[(\d+)\]\s+(.+)', chunk.strip())
        if not m:
            continue
        number = m.group(1)
        title = m.group(2).strip()
        url = _field(chunk, 'URL')
        source = _field(chunk, 'Source')
        published = _field(chunk, 'Published')
        themes_raw = _field(chunk, 'Themes')
        themes = [t.strip() for t in themes_raw.split(',') if t.strip()]
        if url:
            entries.append({
                'number': number,
                'title': title,
                'url': url,
                'source': source,
                'published': published,
                'themes': themes,
            })
    return entries


def _e(s) -> str:
    return html.escape(str(s or ''), quote=True)


def _render_html(entries: list, all_themes: list) -> str:
    # Safe JSON embed: guard against </script> in values
    entries_js = json.dumps(
        [{'number': e['number'], 'title': e['title'], 'url': e['url'],
          'source': e['source'], 'published': e['published'], 'themes': e['themes']}
         for e in entries],
        ensure_ascii=False
    ).replace('</script>', r'<\/script>')
    themes_js = json.dumps(all_themes, ensure_ascii=False).replace('</script>', r'<\/script>')

    lines = []
    a = lines.append  # append shorthand

    a('<!DOCTYPE html>')
    a('<html lang="en">')
    a('<head>')
    a('  <meta charset="utf-8">')
    a('  <meta name="viewport" content="width=device-width, initial-scale=1">')
    a('  <title>Library — AICN</title>')
    a('  <link rel="preconnect" href="https://fonts.googleapis.com">')
    a('  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>')
    a('  <link href="https://fonts.googleapis.com/css2?family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,500;0,8..60,600;0,8..60,700&family=Public+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">')
    a('  <style>')
    a('    * { box-sizing: border-box; }')
    a('    body { margin: 0; }')
    a('    a { color: #2b4a8b; }')
    a('    a.etitle { text-decoration: none; color: #1d2330; }')
    a('    a.etitle:hover { text-decoration: underline; text-decoration-color: #2b4a8b; }')
    a('    button.chip { font: inherit; cursor: pointer; transition: background .12s, color .12s; }')
    a('  </style>')
    a('  <script>')
    a('    ' + _POSTHOG)
    a("    posthog.init('phc_qZHPCa5BvVBCziaXPvLcvUNcaPb6o59bLCURxSmgy9Wy', { api_host: 'https://us.i.posthog.com', person_profiles: 'identified_only' });")
    a('  </script>')
    a('</head>')
    a('<body>')
    a('  <div style="min-height:100vh; background:#eef0f3; font-family:\'Public Sans\',sans-serif; color:#2a2f3a;">')

    # Header — matches index.html with nav links
    a('    <header style="background:#fff; border-bottom:1px solid #e3e6ea;">')
    a('      <div style="max-width:880px; margin:0 auto; padding:28px 28px 24px; display:flex; justify-content:space-between; align-items:flex-end; gap:24px; flex-wrap:wrap;">')
    a('        <div>')
    a('          <div style="display:flex; align-items:baseline; gap:12px;">')
    a('            <a href="index.html" style="font-family:\'Source Serif 4\',serif; font-weight:700; font-size:30px; letter-spacing:-0.01em; color:#1d2330; text-decoration:none;">AICN</a>')
    a('            <span style="font-size:13px; letter-spacing:0.16em; text-transform:uppercase; color:#2b4a8b; font-weight:600;">AI Campaign News</span>')
    a('          </div>')
    a('          <p style="margin:8px 0 0; font-size:14.5px; color:#6b7280; max-width:52ch; line-height:1.5;">Tracking AI use in political campaigns, elections, and issue advocacy.</p>')
    a('        </div>')
    a('        <nav style="display:flex; gap:14px; flex-shrink:0; align-items:center;">')
    a('          <a href="index.html" style="font-size:13px; color:#6b7280; text-decoration:none;">Home</a>')
    a('          <a href="library.html" style="font-size:13px; color:#2b4a8b; font-weight:600; text-decoration:none; border-bottom:2px solid #2b4a8b; padding-bottom:1px;">Library</a>')
    a('          <a href="sources.html" style="font-size:13px; color:#6b7280; text-decoration:none;">Sources</a>')
    a('          <a href="proposals.html" style="font-size:13px; color:#6b7280; text-decoration:none;">Proposals</a>')
    a('          <a href="feed.xml" style="font-size:12.5px; color:#2b4a8b; text-decoration:none; border:1px solid #cdd7ea; padding:4px 11px; border-radius:999px;">RSS</a>')
    a('        </nav>')
    a('      </div>')
    a('    </header>')

    # Main
    a('    <main style="max-width:880px; margin:0 auto; padding:32px 28px 64px;">')
    a('      <div style="margin-bottom:24px;">')
    a('        <h1 style="font-family:\'Source Serif 4\',serif; font-weight:700; font-size:26px; color:#1d2330; margin:0 0 8px;">Research Library</h1>')
    a('        <p style="margin:0; font-size:14.5px; color:#6b7280; max-width:66ch; line-height:1.5;">Hand-curated reference index of research and sources on AI use in political campaigns. Updated manually.</p>')
    a('      </div>')
    a('      <div id="chips" style="display:flex; flex-wrap:wrap; gap:8px; margin-bottom:20px;"></div>')
    a('      <div id="count" style="font-family:\'IBM Plex Mono\',monospace; font-size:12px; color:#9aa1ab; margin-bottom:16px;"></div>')
    a('      <ul id="entries" style="list-style:none; margin:0; padding:0;"></ul>')
    a('    </main>')

    # Footer
    a('    <footer style="background:#fff; border-top:1px solid #e3e6ea;">')
    a('      <div style="max-width:880px; margin:0 auto; padding:24px 28px 36px; font-size:12.5px; color:#8a909b; line-height:1.7;">')
    a('        <p style="margin:0 0 6px;">AICN is a static digest compiled by an automated daily research pipeline that scans news, regulatory, and vendor sources for AI use in political campaigns and elections, then summarizes each item in a neutral, third-party voice.</p>')
    a('        <p style="margin:0;"><a href="index.html" style="color:#2b4a8b; text-decoration:none;">Home</a> · <a href="sources.html" style="color:#2b4a8b; text-decoration:none;">Sources</a> · <a href="proposals.html" style="color:#2b4a8b; text-decoration:none;">Proposals</a> · <a href="feed.xml" style="color:#2b4a8b; text-decoration:none;">RSS feed</a>. Vendor-reported figures are labeled as such and are not independently verified.</p>')
    a('      </div>')
    a('    </footer>')
    a('  </div>')

    # Inline JS — data + renderer
    a('  <script>')
    a('  (function() {')
    a('    var ENTRIES = ' + entries_js + ';')
    a('    var ALL_THEMES = ' + themes_js + ';')
    a('    var active = "all";')
    a('')
    a('    var CHIP_ON  = "background:#2b4a8b;color:#fff;border-color:#2b4a8b;";')
    a('    var CHIP_OFF = "background:#fff;color:#6b7280;border-color:#d4d9e0;";')
    a('    var CHIP_BASE = "font-family:\'Public Sans\',sans-serif;font-size:13px;padding:6px 14px;border-radius:999px;border:1px solid;white-space:nowrap;";')
    a('')
    a('    function esc(s) {')
    a('      return String(s == null ? "" : s)')
    a('        .replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");')
    a('    }')
    a('')
    a('    function render() {')
    a('      var filtered = active === "all" ? ENTRIES : ENTRIES.filter(function(e) {')
    a('        return e.themes.indexOf(active) !== -1;')
    a('      });')
    a('')
    a('      // chips')
    a('      var ch = \'<button class="chip" data-theme="all" style="\' + CHIP_BASE + (active === "all" ? CHIP_ON : CHIP_OFF) + \'">All</button>\';')
    a('      ALL_THEMES.forEach(function(t) {')
    a('        ch += \'<button class="chip" data-theme="\' + esc(t) + \'" style="\' + CHIP_BASE + (active === t ? CHIP_ON : CHIP_OFF) + \'">\' + esc(t) + \'</button>\';')
    a('      });')
    a('      document.getElementById("chips").innerHTML = ch;')
    a('')
    a('      // count')
    a('      document.getElementById("count").textContent = filtered.length + " entr" + (filtered.length === 1 ? "y" : "ies");')
    a('')
    a('      // list')
    a('      var html = "";')
    a('      filtered.forEach(function(e) {')
    a('        var meta = [e.source, e.published].filter(Boolean).join(" · ");')
    a('        html += \'<li style="padding:18px 0; border-bottom:1px solid #e7eaee;">\';')
    a('        html += \'<div style="display:flex; align-items:baseline; gap:8px; margin-bottom:4px;">\';')
    a("        html += '<span style=\"font-family:&quot;IBM Plex Mono&quot;,monospace; font-size:11px; color:#9aa1ab; flex-shrink:0;\">[' + esc(e.number) + ']</span>';")
    a("        html += '<a href=\"' + esc(e.url) + '\" target=\"_blank\" rel=\"noopener\" class=\"etitle\" style=\"font-family:&quot;Source Serif 4&quot;,serif; font-weight:600; font-size:17px; line-height:1.35;\">' + esc(e.title) + '</a>';")

    a('        html += "</div>";')
    a('        if (meta) html += \'<div style="font-family:&quot;IBM Plex Mono&quot;,monospace; font-size:11.5px; color:#9aa1ab; text-transform:uppercase; letter-spacing:0.02em; margin-bottom:8px;">\' + esc(meta) + \'</div>\';')
    a('        if (e.themes.length) {')
    a('          html += \'<div style="display:flex; flex-wrap:wrap; gap:6px;">\';')
    a('          e.themes.forEach(function(t) {')
    a('            html += \'<span style="font-size:10px; padding:2px 9px; border-radius:999px; background:#edf0f4; color:#6b7280; border:1px solid #e0e4ea; font-family:IBM Plex Mono,monospace; letter-spacing:0.04em; text-transform:uppercase;">\' + esc(t) + \'</span>\';')
    a('          });')
    a('          html += "</div>";')
    a('        }')
    a('        html += "</li>";')
    a('      });')
    a('      document.getElementById("entries").innerHTML = html ||')
    a('        \'<li style="padding:32px 0; color:#9aa1ab; font-size:14px;">No entries match this theme.</li>\';')
    a('')
    a('      // chip events')
    a('      var chips = document.querySelectorAll(".chip");')
    a('      for (var i = 0; i < chips.length; i++) {')
    a('        chips[i].addEventListener("click", function(ev) {')
    a('          active = ev.currentTarget.getAttribute("data-theme");')
    a('          render();')
    a('        });')
    a('      }')
    a('    }')
    a('')
    a('    render();')
    a('  })();')
    a('  </script>')
    a('</body>')
    a('</html>')

    return '\n'.join(lines)


def build_library_html(root: str = ROOT) -> str | None:
    """Parse data/library.md and write library.html. Returns output path or None."""
    lib_md = os.path.join(root, 'data', 'library.md')
    if not os.path.exists(lib_md):
        return None
    with open(lib_md, encoding='utf-8') as f:
        md_text = f.read()
    entries = parse_library(md_text)
    if not entries:
        return None

    # Collect unique themes in order of first appearance
    seen: list[str] = []
    for e in entries:
        for t in e['themes']:
            if t not in seen:
                seen.append(t)

    out = os.path.join(root, 'library.html')
    with open(out, 'w', encoding='utf-8') as f:
        f.write(_render_html(entries, seen))
    return out


if __name__ == '__main__':
    path = build_library_html()
    if path:
        print(f'Wrote {path}')
    else:
        print('No data/library.md found — nothing written.')
