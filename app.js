/* AICN — vanilla static renderer. No framework, no build step.
   Reads data/digests.json + data/meta.json sitting next to index.html.
   One continuous reverse-chronological feed (flattened across all runs),
   paginated client-side. Category is shown as a badge per item; chips filter
   the feed rather than sectioning it. */
(function () {
  'use strict';

  var PAGE_SIZE = 20;

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

  var state = { loading: true, error: '', items: [], latestRun: null, meta: null, query: '', activeCategory: 'all', page: 1 };

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
  function itemAnchor(it) { return 'item-' + esc(it.id || ''); }

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

            // Flatten every run's items into one list, then sort
            // reverse-chronologically by published date (falling back to
            // first_seen_run for items missing one), so the feed reads as a
            // single continuous stream rather than day buckets.
            var flat = [];
            runs.forEach(function (r) { (r.items || []).forEach(function (it) { flat.push(it); }); });
            flat.sort(function (a, b) {
              var ad = a.published || a.first_seen_run || '';
              var bd = b.published || b.first_seen_run || '';
              if (ad !== bd) return ad < bd ? 1 : -1;
              var afs = a.first_seen_run || '';
              var bfs = b.first_seen_run || '';
              return afs < bfs ? 1 : (afs > bfs ? -1 : 0);
            });

            state.loading = false;
            state.items = flat;
            state.latestRun = runs[0];
            state.meta = meta;
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

    var run = state.latestRun;
    var q = state.query.trim().toLowerCase();
    function matches(it) {
      return !q
        || String(it.title || '').toLowerCase().indexOf(q) !== -1
        || String(it.summary || '').toLowerCase().indexOf(q) !== -1;
    }
    var order = CATEGORIES.map(function (c) { return c.key; }).concat(['other']);
    var present = {};
    state.items.forEach(function (it) { present[catKeyOf(it)] = true; });

    var filtered = state.items.filter(function (it) {
      return matches(it) && (state.activeCategory === 'all' || catKeyOf(it) === state.activeCategory);
    });

    var totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
    if (state.page > totalPages) state.page = totalPages;
    var pageStart = (state.page - 1) * PAGE_SIZE;
    var pageItems = filtered.slice(pageStart, pageStart + PAGE_SIZE);

    var html = '';

    // hero — latest run's top_summary, with jump-links down to its items
    var runItems = run.items || [];
    var kicker = run.is_light_run ? 'Light run' : 'Latest run';
    var metaLine = fmtDate(run.date || run.run_id) + ' · ' + runItems.length + (runItems.length === 1 ? ' item' : ' items');
    html += '<section style="margin-top:28px; background:#e9eef7; border:1px solid #d8e1f1; border-radius:10px; padding:26px 30px;">';
    html += '<div style="display:flex; align-items:center; gap:10px; margin-bottom:14px; flex-wrap:wrap;">';
    html += '<span style="font-family:\'IBM Plex Mono\',monospace; font-size:10.5px; letter-spacing:0.1em; text-transform:uppercase; color:#fff; background:#2b4a8b; padding:3px 9px; border-radius:4px;">' + esc(kicker) + '</span>';
    html += '<span style="font-family:\'IBM Plex Mono\',monospace; font-size:12px; color:#6b7280;">' + esc(metaLine) + '</span>';
    html += '</div>';
    if (run.is_light_run) {
      html += '<p style="margin:0 0 12px; font-size:13px; color:#8a7330; background:#f4efe2; border:1px solid #e8dec5; padding:8px 12px; border-radius:6px; display:inline-block;">Lighter update than usual — fewer items surfaced in this run.</p>';
    }
    html += '<p style="margin:0; font-family:\'Source Serif 4\',serif; font-size:21px; line-height:1.5; color:#2c3340;">' + esc(run.top_summary || '') + '</p>';
    if (runItems.length) {
      html += '<ul style="list-style:none; margin:16px 0 0; padding:0; display:flex; flex-direction:column; gap:6px;">';
      runItems.forEach(function (it) {
        html += '<li><a href="#' + itemAnchor(it) + '" class="jump-link" data-target="' + itemAnchor(it) + '" style="font-size:13.5px; color:#2b4a8b; text-decoration:none;">&raquo; ' + esc(it.title || '(untitled)') + '</a></li>';
      });
      html += '</ul>';
    }
    html += '</section>';

    // controls
    html += '<div style="position:sticky; top:0; z-index:5; background:#eef0f3; padding:18px 0 14px; margin-top:8px; border-bottom:1px solid #e3e6ea;">';
    html += '<div style="display:flex; gap:10px; align-items:center; margin-bottom:14px; flex-wrap:wrap;">';
    html += '<label for="search" style="position:absolute; width:1px; height:1px; overflow:hidden; clip:rect(0,0,0,0); white-space:nowrap;">Search headlines and summaries</label>';
    html += '<input id="search" type="text" placeholder="Search headlines and summaries" value="' + escAttr(state.query) + '" style="flex:1; min-width:220px; font-family:\'Public Sans\',sans-serif; font-size:14px; padding:9px 14px; border:1px solid #d4d9e0; border-radius:7px; background:#fff; color:#2a2f3a; outline:none;">';
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

    // feed
    var feedHtml = '';
    if (!pageItems.length) {
      var emptyMessage = state.items.length === 0
        ? 'No items surfaced yet.'
        : 'No items match your search or filter.';
      feedHtml = '<div style="padding:64px 0; text-align:center; color:#9aa1ab; font-size:14px;">' + esc(emptyMessage) + '</div>';
    } else {
      pageItems.forEach(function (it) {
        var src = it.source || it.source_domain || 'Source';
        var dl = fmtDate(it.published);
        var ml = dl ? (src + ' · ' + dl) : src;
        var catLabel = CAT_LABEL[catKeyOf(it)] || 'Other';
        feedHtml += '<article id="' + itemAnchor(it) + '" style="padding:20px 0; border-bottom:1px solid #e7eaee;">';
        feedHtml += '<span style="font-size:10.5px; font-family:\'IBM Plex Mono\',monospace; letter-spacing:0.08em; text-transform:uppercase; color:#2b4a8b; background:#e9eef7; padding:2px 8px; border-radius:4px;">' + esc(catLabel) + '</span>';
        feedHtml += '<div style="margin-top:8px;"><a href="' + escAttr(it.url || '#') + '" target="_blank" rel="noopener" class="headline" style="font-family:\'Source Serif 4\',serif; font-weight:600; font-size:19px; line-height:1.35; color:#1d2330; text-decoration:none;">' + esc(it.title || '(untitled)') + '</a></div>';
        feedHtml += '<div style="display:flex; align-items:center; gap:10px; margin:7px 0 10px; flex-wrap:wrap;">';
        feedHtml += '<span style="font-family:\'IBM Plex Mono\',monospace; font-size:11.5px; color:#9aa1ab; text-transform:uppercase; letter-spacing:0.02em;">' + esc(ml) + '</span>';
        (it.flags || []).forEach(function (f) {
          if (!FLAG_LABEL[f]) return;
          feedHtml += '<span style="font-size:11px; padding:2px 8px; border-radius:999px; background:#edf0f4; color:#6b7280; border:1px solid #e0e4ea; font-weight:500;">' + esc(FLAG_LABEL[f]) + '</span>';
        });
        feedHtml += '</div>';
        feedHtml += '<p style="margin:0; font-size:14.5px; line-height:1.6; color:#4b5563;">' + esc(it.summary || '') + '</p>';
        if (it.why_it_matters) {
          feedHtml += '<div style="margin-top:12px; border-left:3px solid #2b4a8b; padding:2px 0 2px 14px;">';
          feedHtml += '<span style="font-family:\'IBM Plex Mono\',monospace; font-size:10.5px; letter-spacing:0.12em; text-transform:uppercase; color:#2b4a8b; font-weight:600;">Notes</span>';
          feedHtml += '<p style="margin:4px 0 0; font-size:14px; line-height:1.55; color:#384152;">' + esc(it.why_it_matters) + '</p></div>';
        }
        feedHtml += '</article>';
      });
    }

    // pagination
    var pagerHtml = '';
    if (totalPages > 1) {
      pagerHtml += '<nav aria-label="Pagination" style="display:flex; align-items:center; justify-content:center; gap:14px; padding:28px 0;">';
      pagerHtml += '<button id="prevPage" ' + (state.page <= 1 ? 'disabled' : '') + ' style="font-family:\'Public Sans\',sans-serif; font-size:13px; padding:7px 16px; border-radius:7px; border:1px solid #d4d9e0; background:#fff; color:' + (state.page <= 1 ? '#c3c8d1' : '#4b5563') + '; cursor:' + (state.page <= 1 ? 'default' : 'pointer') + ';">&larr; Newer</button>';
      pagerHtml += '<span style="font-family:\'IBM Plex Mono\',monospace; font-size:12.5px; color:#6b7280;">Page ' + state.page + ' of ' + totalPages + '</span>';
      pagerHtml += '<button id="nextPage" ' + (state.page >= totalPages ? 'disabled' : '') + ' style="font-family:\'Public Sans\',sans-serif; font-size:13px; padding:7px 16px; border-radius:7px; border:1px solid #d4d9e0; background:#fff; color:' + (state.page >= totalPages ? '#c3c8d1' : '#4b5563') + '; cursor:' + (state.page >= totalPages ? 'default' : 'pointer') + ';">Older &rarr;</button>';
      pagerHtml += '</nav>';
    }

    main.innerHTML = html + feedHtml + pagerHtml;
    wire();
  }

  // --- events -------------------------------------------------------------
  function wire() {
    var search = document.getElementById('search');
    if (search) {
      search.addEventListener('input', function (e) {
        state.query = e.target.value;
        state.page = 1;
        render();
        var s2 = document.getElementById('search');
        if (s2) { s2.focus(); var v = s2.value.length; s2.setSelectionRange(v, v); }
      });
    }
    var chips = document.querySelectorAll('.chip');
    for (var i = 0; i < chips.length; i++) {
      chips[i].addEventListener('click', function (e) {
        state.activeCategory = e.currentTarget.getAttribute('data-cat');
        state.page = 1;
        render();
      });
    }
    var prev = document.getElementById('prevPage');
    if (prev) prev.addEventListener('click', function () { if (state.page > 1) { state.page--; render(); window.scrollTo(0, 0); } });
    var next = document.getElementById('nextPage');
    if (next) next.addEventListener('click', function () { state.page++; render(); window.scrollTo(0, 0); });

    var jumps = document.querySelectorAll('.jump-link');
    for (var j = 0; j < jumps.length; j++) {
      jumps[j].addEventListener('click', function (e) {
        e.preventDefault();
        var target = e.currentTarget.getAttribute('data-target');
        // The target item is always within the most recent items, which sort
        // first — resetting filters to page 1/all/no-query guarantees it's
        // actually rendered before we try to scroll to it.
        state.page = 1;
        state.activeCategory = 'all';
        state.query = '';
        render();
        var el = document.getElementById(target);
        if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
    }
  }

  load();
})();
