/* AICN — vanilla static renderer. No framework, no build step.
   Reads data/digests.json + data/meta.json sitting next to index.html. */
(function () {
  'use strict';

  var CATEGORIES = [
    { key: 'vendor_moves', label: 'Vendor Moves' },
    { key: 'deepfakes', label: 'Deepfakes & Synthetic Media' },
    { key: 'polling_synthetic', label: 'Synthetic Polling' },
    { key: 'regulation', label: 'Regulation & Legal' },
    { key: 'deployments_studies', label: 'Deployments & Studies' },
    { key: 'analysis_oped', label: 'Analysis & Op-Ed' }
  ];
  var CAT_LABEL = {};
  CATEGORIES.forEach(function (c) { CAT_LABEL[c.key] = c.label; });
  var FLAG_LABEL = {
    vendor_self_reported: 'self-reported', contested: 'contested',
    speculative: 'speculative', paywalled: 'paywalled'
  };
  var MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

  var state = { loading: true, error: '', runs: [], meta: null, currentRunId: '', query: '', activeCategory: 'all' };

  var main = document.getElementById('main');
  var lastUpdatedEl = document.getElementById('lastUpdated');

  // --- helpers ------------------------------------------------------------
  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }
  function escAttr(s) { return esc(s); }

  function fmtDate(s) {
    if (!s) return '';
    var p = String(s).split('-');
    if (p.length === 3) {
      var m = MONTHS[parseInt(p[1], 10) - 1];
      if (m) return m + ' ' + parseInt(p[2], 10) + ', ' + p[0];
    }
    return String(s);
  }
  function fmtUpdated(iso) {
    if (!iso) return '—';
    var d = new Date(iso);
    if (isNaN(d.getTime())) return String(iso);
    var pad = function (n) { return String(n).padStart(2, '0'); };
    return MONTHS[d.getUTCMonth()] + ' ' + d.getUTCDate() + ', ' + d.getUTCFullYear()
      + ' · ' + pad(d.getUTCHours()) + ':' + pad(d.getUTCMinutes()) + ' UTC';
  }
  function catKeyOf(it) {
    return CAT_LABEL[it && it.category] ? it.category : 'other';
  }

  // --- data load ----------------------------------------------------------
  function load() {
    fetch('data/digests.json', { cache: 'no-store' })
      .then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      })
      .then(function (digests) {
        return fetch('data/meta.json', { cache: 'no-store' })
          .then(function (mr) { return mr.ok ? mr.json() : null; })
          .catch(function () { return null; })
          .then(function (meta) {
            var runs = (digests.runs || []).slice().sort(function (a, b) {
              return String(b.run_id || '').localeCompare(String(a.run_id || ''));
            });
            if (!runs.length) throw new Error('No runs in digest.');
            state.loading = false;
            state.runs = runs;
            state.meta = meta;
            state.currentRunId = runs[0].run_id;
            render();
          });
      })
      .catch(function (e) {
        state.loading = false;
        state.error = (e && e.message) || 'Unknown error.';
        render();
      });
  }

  // --- render -------------------------------------------------------------
  function render() {
    lastUpdatedEl.textContent =
      state.meta && state.meta.last_updated ? fmtUpdated(state.meta.last_updated) : '—';

    if (state.loading) {
      main.innerHTML = '<div style="padding:90px 0; text-align:center; color:#9aa1ab; font-family:\'IBM Plex Mono\',monospace; font-size:13px;">Loading digest…</div>';
      return;
    }
    if (state.error) {
      main.innerHTML = '<div style="margin-top:32px; padding:20px 24px; background:#fff; border:1px solid #e3c4c4; border-radius:8px; color:#8a2f2a; font-size:14px; line-height:1.5;">Couldn’t load <span style="font-family:\'IBM Plex Mono\',monospace;">data/digests.json</span>. ' + esc(state.error) + '</div>';
      return;
    }

    var run = null;
    for (var i = 0; i < state.runs.length; i++) {
      if (state.runs[i].run_id === state.currentRunId) { run = state.runs[i]; break; }
    }
    if (!run) run = state.runs[0];
    var latestId = state.runs[0] && state.runs[0].run_id;
    var items = run.items || [];
    var q = state.query.trim().toLowerCase();
    function matches(it) {
      return !q
        || String(it.title || '').toLowerCase().indexOf(q) !== -1
        || String(it.summary || '').toLowerCase().indexOf(q) !== -1;
    }
    var filtered = items.filter(matches);
    var order = CATEGORIES.map(function (c) { return c.key; }).concat(['other']);

    var html = '';

    // hero
    var kicker = run.is_light_run ? 'Light run' : 'Latest run';
    var metaLine = fmtDate(run.date || run.run_id) + ' · ' + items.length + (items.length === 1 ? ' item' : ' items');
    html += '<section style="margin-top:28px; background:#e9eef7; border:1px solid #d8e1f1; border-radius:10px; padding:26px 30px;">';
    html += '<div style="display:flex; align-items:center; gap:10px; margin-bottom:14px; flex-wrap:wrap;">';
    html += '<span style="font-family:\'IBM Plex Mono\',monospace; font-size:10.5px; letter-spacing:0.1em; text-transform:uppercase; color:#fff; background:#2b4a8b; padding:3px 9px; border-radius:4px;">' + esc(kicker) + '</span>';
    html += '<span style="font-family:\'IBM Plex Mono\',monospace; font-size:12px; color:#6b7280;">' + esc(metaLine) + '</span>';
    html += '</div>';
    if (run.is_light_run) {
      html += '<p style="margin:0 0 12px; font-size:13px; color:#8a7330; background:#f4efe2; border:1px solid #e8dec5; padding:8px 12px; border-radius:6px; display:inline-block;">Lighter update than usual — fewer items surfaced in this run.</p>';
    }
    html += '<p style="margin:0; font-family:\'Source Serif 4\',serif; font-size:21px; line-height:1.5; color:#2c3340;">' + esc(run.top_summary || '') + '</p>';
    html += '</section>';

    // controls
    var present = {};
    items.forEach(function (it) { present[catKeyOf(it)] = true; });
    html += '<div style="position:sticky; top:0; z-index:5; background:#eef0f3; padding:18px 0 14px; margin-top:8px; border-bottom:1px solid #e3e6ea;">';
    html += '<div style="display:flex; gap:10px; align-items:center; margin-bottom:14px; flex-wrap:wrap;">';
    html += '<label for="search" style="position:absolute; width:1px; height:1px; overflow:hidden; clip:rect(0,0,0,0); white-space:nowrap;">Search headlines and summaries</label>';
    html += '<input id="search" type="text" placeholder="Search headlines and summaries" value="' + escAttr(state.query) + '" style="flex:1; min-width:220px; font-family:\'Public Sans\',sans-serif; font-size:14px; padding:9px 14px; border:1px solid #d4d9e0; border-radius:7px; background:#fff; color:#2a2f3a; outline:none;">';
    html += '<label for="runSelect" style="position:absolute; width:1px; height:1px; overflow:hidden; clip:rect(0,0,0,0); white-space:nowrap;">Select a run by date</label>';
    html += '<select id="runSelect" aria-label="Select a run by date" style="font-family:\'IBM Plex Mono\',monospace; font-size:12.5px; padding:9px 12px; border:1px solid #d4d9e0; border-radius:7px; background:#fff; color:#4b5563; outline:none; cursor:pointer;">';
    state.runs.forEach(function (r) {
      var label = fmtDate(r.date || r.run_id) + (r.run_id === latestId ? '  (latest)' : '');
      html += '<option value="' + escAttr(r.run_id) + '"' + (r.run_id === state.currentRunId ? ' selected' : '') + '>' + esc(label) + '</option>';
    });
    html += '</select>';
    html += '</div>';
    // chips
    html += '<div style="display:flex; flex-wrap:wrap; gap:8px;">';
    var chipBase = "font-family:'Public Sans',sans-serif; font-size:13px; padding:6px 14px; border-radius:999px; cursor:pointer; white-space:nowrap; transition:all .12s;";
    function chipStyle(key) {
      return chipBase + (state.activeCategory === key
        ? ' background:#2b4a8b; color:#fff; border:1px solid #2b4a8b;'
        : ' background:#fff; color:#6b7280; border:1px solid #d4d9e0;');
    }
    html += '<button class="chip" data-cat="all" style="' + chipStyle('all') + '">All</button>';
    order.forEach(function (k) {
      if (present[k]) {
        html += '<button class="chip" data-cat="' + escAttr(k) + '" style="' + chipStyle(k) + '">' + esc(CAT_LABEL[k] || 'Other') + '</button>';
      }
    });
    html += '</div></div>';

    // sections
    var sectionsHtml = '';
    var sectionCount = 0;
    order.forEach(function (k) {
      if (state.activeCategory !== 'all' && state.activeCategory !== k) return;
      var secItems = filtered.filter(function (it) { return catKeyOf(it) === k; });
      if (!secItems.length) return;
      sectionCount++;
      sectionsHtml += '<section style="margin-top:30px;">';
      sectionsHtml += '<div style="display:flex; align-items:center; gap:12px; margin-bottom:2px;">';
      sectionsHtml += '<h2 style="margin:0; font-family:\'Source Serif 4\',serif; font-weight:600; font-size:17px; color:#1d2330;">' + esc(CAT_LABEL[k] || 'Other') + '</h2>';
      sectionsHtml += '<span style="font-family:\'IBM Plex Mono\',monospace; font-size:12px; color:#9aa1ab;">' + secItems.length + '</span>';
      sectionsHtml += '<div style="flex:1; height:1px; background:#e3e6ea;"></div></div>';
      secItems.forEach(function (it) {
        var src = it.source || it.source_domain || 'Source';
        var dl = fmtDate(it.published);
        var ml = dl ? (src + ' · ' + dl) : src;
        sectionsHtml += '<article style="padding:20px 0; border-bottom:1px solid #e7eaee;">';
        sectionsHtml += '<a href="' + escAttr(it.url || '#') + '" target="_blank" rel="noopener" class="headline" style="font-family:\'Source Serif 4\',serif; font-weight:600; font-size:19px; line-height:1.35; color:#1d2330; text-decoration:none;">' + esc(it.title || '(untitled)') + '</a>';
        sectionsHtml += '<div style="display:flex; align-items:center; gap:10px; margin:7px 0 10px; flex-wrap:wrap;">';
        sectionsHtml += '<span style="font-family:\'IBM Plex Mono\',monospace; font-size:11.5px; color:#9aa1ab; text-transform:uppercase; letter-spacing:0.02em;">' + esc(ml) + '</span>';
        (it.flags || []).forEach(function (f) {
          if (!FLAG_LABEL[f]) return;
          sectionsHtml += '<span style="font-size:11px; padding:2px 8px; border-radius:999px; background:#edf0f4; color:#6b7280; border:1px solid #e0e4ea; font-weight:500;">' + esc(FLAG_LABEL[f]) + '</span>';
        });
        sectionsHtml += '</div>';
        sectionsHtml += '<p style="margin:0; font-size:14.5px; line-height:1.6; color:#4b5563;">' + esc(it.summary || '') + '</p>';
        if (it.why_it_matters) {
          sectionsHtml += '<div style="margin-top:12px; border-left:3px solid #2b4a8b; padding:2px 0 2px 14px;">';
          sectionsHtml += '<span style="font-family:\'IBM Plex Mono\',monospace; font-size:10.5px; letter-spacing:0.12em; text-transform:uppercase; color:#2b4a8b; font-weight:600;">Why it matters</span>';
          sectionsHtml += '<p style="margin:4px 0 0; font-size:14px; line-height:1.55; color:#384152;">' + esc(it.why_it_matters) + '</p></div>';
        }
        sectionsHtml += '</article>';
      });
      sectionsHtml += '</section>';
    });

    if (sectionCount === 0) {
      var emptyMessage = items.length === 0
        ? 'No items surfaced in this run.'
        : 'No items match your search in this run.';
      sectionsHtml = '<div style="padding:64px 0; text-align:center; color:#9aa1ab; font-size:14px;">' + esc(emptyMessage) + '</div>';
    }

    main.innerHTML = html + sectionsHtml;
    wire();
  }

  // --- events -------------------------------------------------------------
  function wire() {
    var search = document.getElementById('search');
    if (search) {
      search.addEventListener('input', function (e) {
        state.query = e.target.value;
        render();
        // restore focus + caret after re-render
        var s2 = document.getElementById('search');
        if (s2) { s2.focus(); var v = s2.value.length; s2.setSelectionRange(v, v); }
      });
    }
    var runSelect = document.getElementById('runSelect');
    if (runSelect) {
      runSelect.addEventListener('change', function (e) {
        state.currentRunId = e.target.value;
        state.activeCategory = 'all';
        state.query = '';
        render();
      });
    }
    var chips = document.querySelectorAll('.chip');
    for (var i = 0; i < chips.length; i++) {
      chips[i].addEventListener('click', function (e) {
        state.activeCategory = e.currentTarget.getAttribute('data-cat');
        render();
      });
    }
  }

  load();
})();
