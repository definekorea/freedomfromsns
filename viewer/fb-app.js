/* FreedomFromSNS — local Facebook-archive browser. Pure vanilla, no framework.
 * Everything (browse, calendar, filters, text search) renders client-side from
 * /api/index, so it's instant. Post detail lazy-loads from /api/fb/objects.
 * Semantic search (/api/search) and the AI chat (/api/chat) are Gemini-backed,
 * local-only — no Weft, no apicascade, no cloud middleman.
 */
(function () {
  "use strict";
  var CFG = window.FFS || {};
  var TYPE = { photo: "사진", video: "영상", link: "링크", status: "글", share: "공유", uncat: "미분류" };
  var MON = "일월화수목금토".split("");
  var PAGE = 60;

  var S = {                     // app state
    posts: [], related: {}, byId: {},
    view: "browse",             // browse | calendar | chat
    type: "all", year: "all", q: "",
    shown: PAGE,
    cal: null,                  // {y,m}
    chat: [],                   // [{role:"user"|"bot", content, sources}]
    chatBusy: false,
    semanticIds: null,          // semantic results for the current query (null = none/keyword)
    semanticLoading: false, searchToken: 0,
    model: (function () { try { return localStorage.getItem("ffs.model") || (CFG.defaultModel || "gemini-2.5-flash"); } catch (e) { return CFG.defaultModel || "gemini-2.5-flash"; } })(),
    agent: (function () { try { var v = localStorage.getItem("ffs.agent"); return v === null ? true : v === "1"; } catch (e) { return true; } })(),
  };
  var els = {};

  /* ── boot ───────────────────────────────────────────────────────────── */
  function el(t, c, txt) { var e = document.createElement(t); if (c) e.className = c; if (txt != null) e.textContent = txt; return e; }
  function fmtDate(d) { return d ? d.slice(0, 10) : ""; }

  fetch(CFG.index).then(function (r) { return r.json(); }).then(function (data) {
    S.posts = (data || []).filter(function (p) { return p.date; });
    S.posts.forEach(function (p) { S.byId[p.id] = p; });
    var latest = S.posts.length ? S.posts[0].date : "";
    S.cal = latest ? { y: +latest.slice(0, 4), m: +latest.slice(5, 7) } : { y: new Date().getFullYear(), m: 1 };
    if (CFG.related) fetch(CFG.related).then(function (r) { return r.json(); }).then(function (rel) { S.related = rel || {}; }).catch(function () {});
    loadChat();
    routeFromHash();
    window.addEventListener("hashchange", routeFromHash);
  }).catch(function () { els.main.innerHTML = '<div class="fb-empty">콘텐츠를 불러오지 못했습니다.</div>'; });

  /* ── chrome (header + filters) built once ───────────────────────────── */
  function buildChrome() {
    var top = el("div", "fb-top");
    var bar = el("div", "fb-bar");
    var brand = el("div", "fb-brand"); brand.innerHTML = (CFG.site || "Unattached") + ' <small>아카이브</small>';
    brand.style.cursor = "pointer"; brand.onclick = goHome;

    var tabs = el("div", "fb-tabs");
    els.tabBrowse = el("button", "fb-tab", "둘러보기"); els.tabBrowse.onclick = goHome;
    els.tabCal = el("button", "fb-tab", "달력"); els.tabCal.onclick = function () { location.hash = "#calendar" + (S.q ? "=" + encodeURIComponent(S.q) : ""); };
    tabs.appendChild(els.tabBrowse); tabs.appendChild(els.tabCal);
    if (CFG.chat) {
      els.tabChat = el("button", "fb-tab fb-tab-ai", "✦ AI 대화"); els.tabChat.onclick = function () { location.hash = "#chat"; };
      tabs.appendChild(els.tabChat);
    }

    // Unified search: typing filters instantly by keyword, then auto-enriches
    // with semantic results (페르시아→이란) when the box answers. No Enter needed.
    var search = el("div", "fb-search");
    search.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/></svg>';
    els.q = el("input"); els.q.type = "search"; els.q.placeholder = "검색…";
    var deb;
    els.q.addEventListener("input", function () { clearTimeout(deb); deb = setTimeout(function () { doSearch(els.q.value.trim()); }, 300); });
    els.q.addEventListener("keydown", function (e) { if (e.key === "Enter" && !e.isComposing) { e.preventDefault(); clearTimeout(deb); doSearch(els.q.value.trim()); } });
    search.appendChild(els.q);

    bar.appendChild(brand); bar.appendChild(tabs); bar.appendChild(search);
    top.appendChild(bar);

    els.filters = el("div", "fb-filters");
    top.appendChild(els.filters);
    document.body.appendChild(top);

    els.main = el("div", "fb-main"); document.body.appendChild(els.main);
    buildModal();
  }

  function renderFilters() {
    els.filters.innerHTML = "";
    if (S.view !== "browse") return;
    // Two groups: shown-by-default content, then a divider, then "click-into"
    // buckets (링크/공유/미분류) that are hidden from 전체 — you open them on demand.
    function chip(t, sec) {
      var c = el("button", "fb-chip" + (sec ? " sec" : "") + (S.type === t ? " on" : ""), t === "all" ? "전체" : TYPE[t]);
      c.dataset.t = t; c.onclick = function () { S.type = t; S.shown = PAGE; renderBrowse(); };
      return c;
    }
    ["all", "photo", "video", "status"].forEach(function (t) { els.filters.appendChild(chip(t, false)); });
    els.filters.appendChild(el("div", "fb-chip-div"));
    ["link", "share", "uncat"].forEach(function (t) { els.filters.appendChild(chip(t, true)); });
    els.filters.appendChild(el("div", "fb-sp"));
    var yrs = uniqueYears();
    var sel = el("select", "fb-year");
    sel.appendChild(new Option("모든 연도", "all"));
    yrs.forEach(function (y) { sel.appendChild(new Option(y + "년", y)); });
    sel.value = S.year; sel.onchange = function () { S.year = sel.value; S.shown = PAGE; renderBrowse(); };
    els.filters.appendChild(sel);
    els.count = el("div", "fb-count"); els.filters.appendChild(els.count);
  }

  function uniqueYears() { var s = {}; S.posts.forEach(function (p) { s[p.date.slice(0, 4)] = 1; }); return Object.keys(s).sort().reverse(); }

  /* ── routing ────────────────────────────────────────────────────────── */
  //  Hash forms: #browse | #calendar | #chat | #post/<id> | #<view>=<query>.
  //  The search query lives in the URL so it's restorable + back/forward-safe;
  //  doSearch updates it with replaceState (no history pile-up per keystroke).
  function renderCurrentView() {
    if (S.view === "calendar") renderCalendar();
    else if (S.view === "chat") renderChat();
    else renderBrowse();
  }
  function routeFromHash() {
    if (!els.main) buildChrome();
    var h = location.hash.slice(1);
    if (h.indexOf("post/") === 0) { var pid = h.slice(5); try { pid = decodeURIComponent(pid); } catch (e) {} openDetail(pid); return; }
    closeModal();
    var eq = h.indexOf("="), view = eq >= 0 ? h.slice(0, eq) : h;
    var q = "";
    if (eq >= 0) { try { q = decodeURIComponent(h.slice(eq + 1)); } catch (e) { q = h.slice(eq + 1); } }
    S.view = (view === "calendar") ? "calendar" : (view === "chat" && CFG.chat) ? "chat" : "browse";
    els.tabBrowse.classList.toggle("on", S.view === "browse");
    els.tabCal.classList.toggle("on", S.view === "calendar");
    if (els.tabChat) els.tabChat.classList.toggle("on", S.view === "chat");
    // sync the search state to the URL (so back/forward restores it cleanly).
    // Chat carries no query — leave the search bar untouched while in it.
    if (S.view !== "chat" && q !== S.q) {
      S.q = q; S.semanticIds = null; S.shown = PAGE; var token = ++S.searchToken;
      if (els.q) els.q.value = q;
      if (q && q.length >= 2 && CFG.search) { S.semanticLoading = true; fireSemantic(q, token); }
      else S.semanticLoading = false;
    }
    renderFilters();
    renderCurrentView();
  }

  /* ── unified search: instant keyword filter, then auto-enrich with semantic
     (same box retrieval as the chat — Gemini + expansion, 페르시아→이란). Filters
     whichever view you're on (grid OR calendar). The query lives in the URL via
     replaceState — so it never adds a back-button stop, yet survives refresh and
     restores on back/forward. Each keystroke supersedes the last (token). ──── */
  function fireSemantic(v, token) {
    fetch(CFG.search, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ query: v }) })
      .then(function (r) { return r.json(); })
      .then(function (res) { if (token !== S.searchToken) return; S.semanticLoading = false; S.semanticIds = (res.ids && res.ids.length) ? res.ids : null; renderCurrentView(); })
      .catch(function () { if (token !== S.searchToken) return; S.semanticLoading = false; renderCurrentView(); });
  }
  function doSearch(v) {
    if (S.view === "chat") S.view = "browse";  // search applies to browse/calendar, not chat
    var base = S.view === "calendar" ? "calendar" : "browse";
    var want = "#" + base + (v ? "=" + encodeURIComponent(v) : "");
    if (("#" + location.hash.slice(1)) !== want) {
      // Starting a search from a no-query view = a new history entry, so browser-
      // back returns to the plain browse page. Refining/clearing an existing
      // query replaces (no per-keystroke pile-up).
      var hadQuery = !!S.q;
      if (!hadQuery && v && location.hash.indexOf("#post/") !== 0) history.pushState(null, "", want);
      else history.replaceState(null, "", want);
    }
    var token = ++S.searchToken;
    S.q = v; S.semanticIds = null; S.semanticLoading = !!(v && v.length >= 2 && CFG.search); S.shown = PAGE;
    if (els.q && els.q.value !== v) els.q.value = v;
    els.tabBrowse.classList.toggle("on", S.view === "browse");
    els.tabCal.classList.toggle("on", S.view === "calendar");
    if (els.tabChat) els.tabChat.classList.toggle("on", false);
    renderCurrentView();           // instant keyword first
    if (S.semanticLoading) fireSemantic(v, token);
  }
  // Logo + 둘러보기 → clean default screen (clear search + filters); replaceState
  // so it doesn't add a back stop.
  function goHome() {
    S.searchToken++; S.semanticIds = null; S.semanticLoading = false;
    S.q = ""; S.type = "all"; S.year = "all"; S.shown = PAGE; S.view = "browse";
    if (els.q) els.q.value = "";
    if (location.hash !== "#browse") history.replaceState(null, "", "#browse");
    els.tabBrowse.classList.toggle("on", true);
    els.tabCal.classList.toggle("on", false);
    if (els.tabChat) els.tabChat.classList.toggle("on", false);
    renderFilters(); renderCurrentView();
  }

  /* ── browse grid (filter + paginate, instant) ───────────────────────── */
  function baseList() {
    if (S.semanticIds) return S.semanticIds.map(function (id) { return S.byId[id]; }).filter(Boolean);
    var q = S.q.toLowerCase();
    return S.posts.filter(function (p) { return !q || (p.title + " " + (p.excerpt || "")).toLowerCase().indexOf(q) >= 0; });
  }
  var BUCKETS = { link: 1, share: 1, uncat: 1 };  // click-into; hidden from 전체
  function passType(p) {
    if (S.type === "all") return !BUCKETS[p.type] && !p.empty;   // default feed: real content only
    if (BUCKETS[S.type]) return p.type === S.type;               // a bucket shows its whole type
    return p.type === S.type && !p.empty;                        // 사진/영상/글: hide empties too
  }
  function passYear(p) { return S.year === "all" || p.date.slice(0, 4) === S.year; }
  function filtered() {
    return baseList().filter(function (p) { return passType(p) && passYear(p); });
  }

  function card(p) {
    // Uncategorized media are "just images" — clicking one opens the full-screen
    // lightbox over the WHOLE 미분류 set so you can navigate them all with the
    // thumbnail strip, instead of a text-less detail modal.
    var c = el("div", "fb-card"); c.onclick = function () { if (p.type === "uncat") openUncatLightbox(p); else openPost(p.id); };
    var thumb;
    if (p.thumb) { thumb = el("div", "fb-thumb"); var im = el("img"); im.loading = "lazy"; im.src = p.thumb; im.onerror = function () { thumb.classList.add("ph"); thumb.dataset.ic = p.vid ? "▶" : "▦"; im.remove(); }; thumb.appendChild(im); if (p.vid) thumb.appendChild(el("span", "fb-thumb-play", "▶")); }
    else { thumb = el("div", "fb-thumb ph"); thumb.dataset.ic = p.type === "video" || p.type === "uncat" ? "▶" : p.type === "link" ? "🔗" : p.type === "share" ? "↻" : "▦"; }
    var badge = el("div", "fb-badge " + p.type, TYPE[p.type] || "글"); thumb.appendChild(badge);
    c.appendChild(thumb);
    var body = el("div", "fb-body");
    body.appendChild(el("div", "fb-date", fmtDate(p.date)));
    // Facebook posts have no real title — `title` is just the first line of text —
    // so show ONE prominent text preview, not the same line twice.
    var textEl = el("div", "fb-text", p.preview || p.excerpt || p.title || "");
    body.appendChild(textEl);
    c.appendChild(body);
    // link cards show the ACTUAL link preview (image + headline/site) instead of a 🔗
    if (p.type === "link" && p.link_url && !p.thumb) enrichLinkCard(p, thumb, textEl, body);
    return c;
  }
  function enrichLinkCard(p, thumb, textEl, body) {
    unfurl(p.link_url).then(function (d) {
      if (!d || !d.ok) return;
      if (d.image) {
        thumb.classList.remove("ph"); thumb.removeAttribute("data-ic");
        var im = el("img"); im.loading = "lazy"; im.src = d.image;
        im.onerror = function () { im.remove(); thumb.classList.add("ph"); thumb.dataset.ic = "🔗"; };
        thumb.appendChild(im);
      }
      // no real comment (just "shared a link" or empty) → lead with the headline
      var generic = !(p.preview && p.preview.trim()) || /shared a (link|post|memory)/i.test(p.title || "");
      if (d.title && generic) textEl.textContent = decodeEnt(d.title);
      if (d.site) body.appendChild(el("div", "fb-text-site", decodeEnt(d.site)));
    });
  }

  function renderBrowse() {
    renderFilters();
    els.main.innerHTML = "";
    var list = filtered();
    if (els.count) {
      var note = S.semanticLoading ? "  ·  관련 글 찾는 중…" : (S.semanticIds && S.q ? "  ·  의미 검색" : "");
      els.count.textContent = list.length.toLocaleString() + "개" + note;
    }
    if (!list.length) {
      els.main.appendChild(el("div", "fb-empty", S.semanticLoading ? "검색 중…" : "결과가 없습니다."));
      return;
    }
    var grid = el("div", "fb-grid");
    list.slice(0, S.shown).forEach(function (p) { grid.appendChild(card(p)); });
    els.main.appendChild(grid);
    if (S.shown < list.length) {
      var sentinel = el("div", "fb-sentinel");
      els.main.appendChild(sentinel);
      var io = new IntersectionObserver(function (en) { if (en[0].isIntersecting) { io.disconnect(); S.shown += PAGE; renderBrowse(); } });
      io.observe(sentinel);
    }
  }

  /* ── calendar (respects the active search/filter — a temporal view of it) ─ */
  function renderCalendar() {
    var posts = filtered();
    var byDate = {}; posts.forEach(function (p) { (byDate[p.date.slice(0, 10)] = byDate[p.date.slice(0, 10)] || []).push(p); });
    var yrs = Object.keys(posts.reduce(function (a, p) { a[p.date.slice(0, 4)] = 1; return a; }, {})).sort().reverse();
    // if the current month has no matches, jump to the most recent one that does
    if (S.q && yrs.length && yrs.indexOf(String(S.cal.y)) < 0) {
      var latest = posts.map(function (p) { return p.date; }).sort().reverse()[0];
      if (latest) S.cal = { y: +latest.slice(0, 4), m: +latest.slice(5, 7) };
    }
    els.main.innerHTML = "";
    if (S.q) {
      els.main.appendChild(el("div", "fb-cal-search", "‘" + S.q + "’ 검색" +
        (S.semanticLoading ? "  ·  관련 글 찾는 중…" : (S.semanticIds ? "  ·  의미 검색" : "")) +
        "  —  " + posts.length.toLocaleString() + "개"));
    }
    var wrap = el("div", "fb-cal");
    var side = el("div", "fb-cal-side");
    yrs.forEach(function (y) {
      var n = posts.filter(function (p) { return p.date.indexOf(y) === 0; }).length;
      var b = el("button", "fb-cal-y" + (S.cal.y == y ? " on" : ""), y + " (" + n + ")");
      b.onclick = function () { var ds = posts.filter(function (p) { return p.date.indexOf(y) === 0; }).map(function (p) { return p.date; }).sort().reverse()[0]; S.cal = { y: +y, m: ds ? +ds.slice(5, 7) : 12 }; renderCalendar(); };
      side.appendChild(b);
    });
    if (!yrs.length) side.appendChild(el("div", "fb-cal-empty", "결과 없음"));
    wrap.appendChild(side);

    var main = el("div", "fb-cal-main");
    // A sparse year (few posts — incl. any search) shows a compact by-date agenda
    // instead of a 12-month grid you'd have to click through. Dense years → grid.
    var yearPosts = posts.filter(function (p) { return p.date.indexOf(String(S.cal.y)) === 0; })
      .sort(function (a, b) { return a.date < b.date ? 1 : -1; });
    if (yearPosts.length && yearPosts.length <= 50) {
      main.appendChild(el("div", "fb-cal-head2", S.cal.y + "년  ·  " + yearPosts.length + "개"));
      var ag = el("div", "fb-agenda"), lastDay = "";
      yearPosts.forEach(function (p) {
        var day = p.date.slice(0, 10);
        if (day !== lastDay) { ag.appendChild(el("div", "fb-agenda-date", day)); lastDay = day; }
        var row = el("div", "fb-agenda-row");
        row.appendChild(el("span", "fb-badge " + p.type, TYPE[p.type] || "글"));
        row.appendChild(el("span", "fb-agenda-t", p.title || "(무제)"));
        row.onclick = function () { openPost(p.id); };
        ag.appendChild(row);
      });
      main.appendChild(ag);
    } else {
      var head = el("div", "fb-cal-head");
      var prev = el("button", "fb-nav", "‹"); prev.onclick = function () { step(-1); };
      var next = el("button", "fb-nav", "›"); next.onclick = function () { step(1); };
      head.appendChild(prev); head.appendChild(el("div", "fb-cal-title", S.cal.y + "년 " + S.cal.m + "월")); head.appendChild(next);
      main.appendChild(head);
      var g = el("div", "fb-cal-grid");
      MON.forEach(function (d) { g.appendChild(el("div", "fb-dow", d)); });
      var start = new Date(S.cal.y, S.cal.m - 1, 1).getDay();
      var days = new Date(S.cal.y, S.cal.m, 0).getDate();
      for (var i = 0; i < start; i++) g.appendChild(el("div", "fb-cell empty"));
      for (var d = 1; d <= days; d++) {
        var ds = S.cal.y + "-" + ("0" + S.cal.m).slice(-2) + "-" + ("0" + d).slice(-2);
        var dayItems = byDate[ds] || [];
        var cell = el("div", "fb-cell" + (dayItems.length ? " has" : ""));
        var n = el("div", "fb-cell-n", String(d));
        if (dayItems.length) { n.onclick = dayClicker(ds, dayItems); }  // expand the day
        cell.appendChild(n);
        dayItems.slice(0, 4).forEach(function (p) {
          var a = el("div", "fb-ev " + p.type, p.title || "(무제)"); a.title = p.excerpt || p.title || "";
          a.onclick = function () { openPost(p.id); };
          cell.appendChild(a);
        });
        if (dayItems.length > 4) {
          var more = el("div", "fb-more", "+" + (dayItems.length - 4) + " 더보기");
          more.onclick = dayClicker(ds, dayItems);
          cell.appendChild(more);
        }
        g.appendChild(cell);
      }
      main.appendChild(g);
    }
    wrap.appendChild(main); els.main.appendChild(wrap);
  }
  function step(d) { var m = S.cal.m + d, y = S.cal.y; if (m < 1) { m = 12; y--; } if (m > 12) { m = 1; y++; } S.cal = { y: y, m: m }; renderCalendar(); }

  /* ── day panel: expand a crowded calendar day into a clean, scrollable list
     you can click through, then collapse (× / Esc / backdrop) ─────────────── */
  function dayClicker(ds, items) { return function (e) { if (e) e.stopPropagation(); openDayPanel(ds, items); }; }
  function buildDayPanel() {
    els.dayPop = el("div", "fb-daypop");
    var card = el("div", "fb-daypop-card");
    var bar = el("div", "fb-daypop-bar");
    els.dayPopTitle = el("div", "fb-daypop-title");
    var x = el("button", "fb-x", "×"); x.title = "닫기"; x.onclick = closeDayPanel;
    bar.appendChild(els.dayPopTitle); bar.appendChild(x);
    els.dayPopList = el("div", "fb-daypop-list");
    card.appendChild(bar); card.appendChild(els.dayPopList);
    els.dayPop.appendChild(card);
    els.dayPop.addEventListener("click", function (e) { if (e.target === els.dayPop) closeDayPanel(); });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape" && els.dayPop && els.dayPop.classList.contains("on")) closeDayPanel(); });
    document.body.appendChild(els.dayPop);
  }
  function openDayPanel(ds, items) {
    if (!els.dayPop) buildDayPanel();
    els.dayPopTitle.textContent = ds + "  ·  " + items.length + "개";
    els.dayPopList.innerHTML = "";
    items.forEach(function (p) {
      var row = el("div", "fb-agenda-row");
      row.appendChild(el("span", "fb-badge " + p.type, TYPE[p.type] || "글"));
      var t = el("span", "fb-agenda-t", p.title || "(무제)");
      row.appendChild(t);
      if (p.thumb) { var im = el("img", "fb-daypop-thumb"); im.loading = "lazy"; im.src = p.thumb; im.onerror = function () { im.remove(); }; row.appendChild(im); }
      row.onclick = function () { closeDayPanel(); openPost(p.id); };
      els.dayPopList.appendChild(row);
    });
    els.dayPop.classList.add("on"); document.body.style.overflow = "hidden";
    els.dayPopList.scrollTop = 0;
  }
  function closeDayPanel() { if (els.dayPop) els.dayPop.classList.remove("on"); document.body.style.overflow = ""; }

  /* ── detail modal (lazy WP REST) ────────────────────────────────────── */
  function buildModal() {
    els.modal = el("div", "fb-modal");
    els.modal.addEventListener("click", function (e) { if (e.target === els.modal) closePost(); });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape" && els.modal.classList.contains("on")) closePost(); });
    document.body.appendChild(els.modal);
  }
  function closeModal() {
    if (!els.modal) return;
    // stop any playing media — hiding the modal alone leaves the <video> playing.
    els.modal.querySelectorAll("video,audio").forEach(function (v) { try { v.pause(); v.removeAttribute("src"); v.load(); } catch (e) { } });
    els.modal.classList.remove("on"); document.body.style.overflow = "";
  }
  // Close the post the SAME way regardless of trigger (× / Esc / backdrop): pop
  // the #post history entry so the URL, history, and view stay in sync. (The ×,
  // Esc, and backdrop all used to differ — Esc/backdrop just hid the modal and
  // left the hash stuck at #post, which made the back button behave oddly.)
  function closePost() {
    if (location.hash.indexOf("#post/") === 0 && history.length > 1) history.back();
    else if (location.hash.indexOf("#post/") === 0) location.hash = "#browse";
    else closeModal();
  }

  function openDetail(id) {
    var p = S.byId[id];
    els.modal.classList.add("on"); document.body.style.overflow = "hidden";
    els.modal.innerHTML = "";
    var doc = el("div", "fb-doc");
    var bar = el("div", "fb-doc-bar");
    var x = el("button", "fb-x", "×"); x.onclick = closePost;
    bar.appendChild(x);
    bar.appendChild(el("div", "fb-date", p ? fmtDate(p.date) : ""));
    if (p && p.url) { var o = el("a", "fb-orig", "원문 보기 ↗"); o.href = p.url; o.target = "_blank"; o.rel = "noopener"; bar.appendChild(o); }
    doc.appendChild(bar);
    var body = el("div", "fb-doc-body");
    body.innerHTML = '<div class="fb-loading">불러오는 중…</div>';
    doc.appendChild(body);
    els.modal.appendChild(doc);
    els.modal.scrollTop = 0;

    fetch(CFG.object + encodeURIComponent(id))
      .then(function (r) { if (!r.ok) throw 0; return r.json(); })
      .then(function (obj) {
        body.innerHTML = "";
        body.appendChild(el("h1", null, obj.title || (p ? p.title : "")));
        var content = el("div", "fb-doc-md");
        // drop YAML frontmatter + the leading "# title" (shown as <h1> above),
        // then render markdown; archive images are /api/fb/files URLs, made
        // lightbox-clickable below.
        var md = (obj.content_markdown || "")
          .replace(/^---\n[\s\S]*?\n---\n+/, "")
          .replace(/^#\s+.*\n+/, "");
        // pull out local videos ([▶ caption](/api/fb/files…mp4)) — they're
        // relative URLs the link renderer skips, so render them as real <video>
        // players below instead of leaking raw markdown.
        var vids = [];
        md = md.replace(/\[▶[^\]]*\]\((\/api\/fb\/files[^)\s]+)\)/g, function (_, u) { vids.push(u); return ""; });
        content.innerHTML = mdToHtml(md);
        body.appendChild(content);
        vids.forEach(function (u, vi) { var v = el("video", "fb-doc-vid"); v.src = u; v.controls = true; v.preload = "metadata"; v.playsInline = true; if (vi === 0) v.autoplay = true; content.appendChild(v); if (vi === 0) v.play().catch(function () { }); });
        var imgs = content.querySelectorAll("img.fb-md-img");
        var media = []; imgs.forEach(function (im) { media.push({ url: im.getAttribute("src"), type: "image", post_id: id, post_title: obj.title || "" }); });
        imgs.forEach(function (im, ix) { im.style.cursor = "zoom-in"; im.onclick = function () { openLightbox(media, ix); }; });
        appendLinkPreviews(content);
        appendRelated(doc, id);
      })
      .catch(function () {
        body.innerHTML = "";
        body.appendChild(el("h1", null, p ? p.title : ""));
        if (p && p.excerpt) body.appendChild(el("p", null, p.excerpt));
        var note = el("p", "fb-off", "본문을 불러올 수 없습니다.");
        if (p && p.url) { var a = el("a", "fb-orig", "원문 보기 ↗"); a.href = p.url; a.target = "_blank"; note.appendChild(document.createTextNode(" ")); note.appendChild(a); }
        body.appendChild(note);
        appendRelated(doc, id);
      });
  }

  function appendRelated(doc, id) {
    var ids = (S.related[id] || []).map(function (rid) { return S.byId[rid]; }).filter(Boolean).slice(0, 8);
    if (!ids.length) return;
    var rel = el("div", "fb-rel"); rel.appendChild(el("h3", null, "관련 글"));
    var grid = el("div", "fb-rel-grid");
    ids.forEach(function (rp) {
      var c = el("div", "fb-rel-card"); c.onclick = function () { openPost(rp.id); };
      if (rp.thumb) { var im = el("img", "ri"); im.loading = "lazy"; im.src = rp.thumb; im.onerror = function () { im.remove(); }; c.appendChild(im); }
      c.appendChild(el("div", "rt", rp.title || "(무제)"));
      grid.appendChild(c);
    });
    rel.appendChild(grid); doc.appendChild(rel);
  }

  /* ── link previews (unfurl the original — shared links, reshared posts) ───
     FreedomFromSNS isn't self-contained: when a post links out (Instagram /
     YouTube / news / a Facebook permalink), fetch its Open-Graph preview and
     show a rich card that opens the original. Server caches to disk + falls
     back to the Wayback Machine for dead links. */
  var unfurlCache = {};
  function unfurl(u) {
    if (!unfurlCache[u]) unfurlCache[u] = fetch(CFG.unfurl + "?url=" + encodeURIComponent(u))
      .then(function (r) { return r.json(); }).catch(function () { return { ok: false, url: u }; });
    return unfurlCache[u];
  }
  function decodeEnt(s) { if (!s) return ""; var t = el("textarea"); t.innerHTML = s; return t.value; }
  function appendLinkPreviews(content) {
    if (!CFG.unfurl) return;
    var seen = {}, urls = [];
    content.querySelectorAll('a[href^="http"]').forEach(function (a) {
      var u = a.getAttribute("href");
      // Facebook blocks scraping → unfurl always fails; the inline 📘 "Facebook에서
      // 보기" link already opens the original, so don't add a dead preview card.
      if (u && !seen[u] && !/(^|\.)facebook\.com/.test(u)) { seen[u] = 1; urls.push(u); }
    });
    if (!urls.length) return;
    var wrap = el("div", "fb-prev-wrap"); content.appendChild(wrap);
    urls.slice(0, 4).forEach(function (u) {
      var card = el("a", "fb-prev loading"); card.href = u; card.target = "_blank"; card.rel = "noopener";
      card.appendChild(el("div", "fb-prev-body", "링크 미리보기…"));
      wrap.appendChild(card);
      unfurl(u).then(function (d) {
        card.classList.remove("loading"); card.innerHTML = "";
        if (d && d.ok && d.image) { var im = el("img", "fb-prev-img"); im.loading = "lazy"; im.src = d.image; im.onerror = function () { im.remove(); }; card.appendChild(im); }
        var b = el("div", "fb-prev-body");
        var site = (d && d.ok && d.site) ? decodeEnt(d.site) : (function () { try { return new URL(u).hostname.replace(/^www\./, ""); } catch (e) { return "원본"; } })();
        b.appendChild(el("div", "fb-prev-site", site + "  ↗"));
        b.appendChild(el("div", "fb-prev-title", (d && d.ok && decodeEnt(d.title)) || u));
        if (d && d.ok && d.description) b.appendChild(el("div", "fb-prev-desc", decodeEnt(d.description)));
        card.appendChild(b);
      });
    });
  }

  // Open a post WITHOUT stacking history: first open pushes one entry; navigating
  // post→post replaces it. So browser-back closes the post once and returns to
  // the underlying view — never cycling through every post you peeked at.
  function openPost(id) {
    id = String(id);
    if (location.hash.indexOf("#post/") === 0) { history.replaceState(null, "", "#post/" + encodeURIComponent(id)); openDetail(id); }
    else location.hash = "#post/" + encodeURIComponent(id);
  }

  function mediaIndex(media, url) { for (var i = 0; i < media.length; i++) if (media[i].url === url) return i; return -1; }

  /* ── lightbox: full-screen media viewer with prev/next, thumb strip, swipe ── */
  function buildLightbox() {
    els.lb = el("div", "fb-lb");
    var top = el("div", "fb-lb-top");
    var x = el("button", "fb-lb-x", "×"); x.title = "닫기"; x.onclick = closeLightbox;
    els.lbLink = el("a", "fb-lb-link"); els.lbLink.target = "_blank"; els.lbLink.rel = "noopener";
    top.appendChild(x); top.appendChild(els.lbLink);
    els.lbStage = el("div", "fb-lb-stage");
    var prev = el("button", "fb-lb-nav prev", "‹"); prev.onclick = function (e) { e.stopPropagation(); lbGo(-1); };
    var next = el("button", "fb-lb-nav next", "›"); next.onclick = function (e) { e.stopPropagation(); lbGo(1); };
    els.lbCounter = el("div", "fb-lb-count");
    // position scrubber — jump to any image even across thousands of items
    els.lbRange = el("input"); els.lbRange.type = "range"; els.lbRange.min = 0; els.lbRange.className = "fb-lb-range"; els.lbRange.title = "위치로 이동";
    els.lbRange.addEventListener("input", function () { if (!S.lb) return; S.lb.i = +els.lbRange.value; lbRenderStage(); });
    els.lbRange.addEventListener("change", function () { if (!S.lb) return; S.lb.i = +els.lbRange.value; lbRender(); lbEnsureWindow(); });
    els.lbThumbs = el("div", "fb-lb-thumbs");
    els.lb.appendChild(top); els.lb.appendChild(prev); els.lb.appendChild(els.lbStage); els.lb.appendChild(next);
    els.lb.appendChild(els.lbCounter); els.lb.appendChild(els.lbRange); els.lb.appendChild(els.lbThumbs);
    els.lb.addEventListener("click", function (e) { if (e.target === els.lb || e.target === els.lbStage) closeLightbox(); });
    document.addEventListener("keydown", function (e) {
      if (!S.lb) return;
      if (e.key === "Escape") closeLightbox(); else if (e.key === "ArrowLeft") lbGo(-1); else if (e.key === "ArrowRight") lbGo(1);
    });
    // swipe on the stage
    var sx = null;
    els.lbStage.addEventListener("touchstart", function (e) { sx = e.touches[0].clientX; }, { passive: true });
    els.lbStage.addEventListener("touchend", function (e) { if (sx == null) return; var dx = e.changedTouches[0].clientX - sx; if (Math.abs(dx) > 40) lbGo(dx < 0 ? 1 : -1); sx = null; });
    document.body.appendChild(els.lb);
  }
  function openLightbox(items, i) {
    items = (items || []).filter(function (x) { return x && x.url; });
    if (!items.length) return;
    if (!els.lb) buildLightbox();
    S.lb = { items: items, i: Math.min(i || 0, items.length - 1) };
    els.lb.classList.add("on"); document.body.style.overflow = "hidden";
    lbRender(); renderLbThumbs();
  }
  function closeLightbox() { if (els.lb) { els.lb.classList.remove("on"); els.lbStage.innerHTML = ""; } document.body.style.overflow = ""; S.lb = null; }
  function lbGo(d) { if (!S.lb) return; var n = S.lb.items.length; S.lb.i = (S.lb.i + d + n) % n; lbRender(); lbEnsureWindow(); }
  function lbRenderStage() {
    var it = S.lb.items[S.lb.i];
    els.lbStage.innerHTML = "";
    if (it.type === "video") { var v = el("video"); v.src = it.url; v.controls = true; v.autoplay = true; v.playsInline = true; els.lbStage.appendChild(v); }
    else { var im = el("img"); im.src = it.url; im.alt = it.post_title || ""; els.lbStage.appendChild(im); }
    var href = it.post_url || (it.post_id && S.byId[String(it.post_id)] ? "#post/" + it.post_id : "");
    if (href) { els.lbLink.href = href; els.lbLink.textContent = (it.post_title ? it.post_title.slice(0, 46) + "  " : "") + "원문 ↗"; els.lbLink.style.display = ""; }
    else els.lbLink.style.display = "none";
    els.lbCounter.textContent = (S.lb.i + 1) + " / " + S.lb.items.length;
    if (els.lbRange) { els.lbRange.max = S.lb.items.length - 1; els.lbRange.value = S.lb.i; }
  }
  function lbRender() { lbRenderStage(); lbHighlight(); }
  // The strip can hold thousands of items (the whole 미분류 set), so keep only a
  // window of thumbnails in the DOM — but EXTEND it by appending/prepending (never
  // clearing) so navigation is smooth with no flashing rebuild, and always keep a
  // generous buffer (LB_MARGIN) ahead so thumbs load well before you reach the end.
  var LB_WIN = 30, LB_MARGIN = 15, LB_MAX = 240;
  function lbThumb(k) {
    var it = S.lb.items[k];
    var t = el("div", "fb-lb-thumb" + (it.type === "video" ? " vid" : ""));
    t.dataset.idx = k;
    var im = el("img"); im.loading = "lazy"; im.src = it.thumb || it.url;
    im.onerror = (function (tt) { return function () { tt.classList.add("err"); }; })(t);
    t.appendChild(im);
    t.onclick = (function (idx) { return function () { S.lb.i = idx; lbRender(); lbEnsureWindow(); }; })(k);
    return t;
  }
  function renderLbThumbs() {  // full (re)build centered on the current image
    els.lbThumbs.innerHTML = "";
    if (!S.lb) return;
    var n = S.lb.items.length, i = S.lb.i;
    S.lb.winStart = Math.max(0, i - LB_WIN);
    S.lb.winEnd = Math.min(n, i + LB_WIN + 1);
    for (var k = S.lb.winStart; k < S.lb.winEnd; k++) els.lbThumbs.appendChild(lbThumb(k));
    lbHighlight(); lbCenterThumb();
  }
  function lbHighlight() { var kids = els.lbThumbs.children; for (var k = 0; k < kids.length; k++) kids[k].classList.toggle("on", +kids[k].dataset.idx === S.lb.i); }
  function lbEnsureWindow() {
    if (!S.lb) return;
    var n = S.lb.items.length, i = S.lb.i;
    // jumped outside the window (e.g. wrap-around) or it grew too big → rebuild once
    if (i < S.lb.winStart || i >= S.lb.winEnd || (S.lb.winEnd - S.lb.winStart) > LB_MAX) { renderLbThumbs(); return; }
    while (S.lb.winEnd < n && i >= S.lb.winEnd - LB_MARGIN) {       // append forward
      els.lbThumbs.appendChild(lbThumb(S.lb.winEnd)); S.lb.winEnd++;
    }
    while (S.lb.winStart > 0 && i < S.lb.winStart + LB_MARGIN) {    // prepend backward
      S.lb.winStart--;
      var before = els.lbThumbs.scrollWidth;
      els.lbThumbs.insertBefore(lbThumb(S.lb.winStart), els.lbThumbs.firstChild);
      els.lbThumbs.scrollLeft += els.lbThumbs.scrollWidth - before;  // keep visual position
    }
    lbHighlight(); lbCenterThumb();
  }
  function lbCenterThumb() { var kids = els.lbThumbs.children; for (var k = 0; k < kids.length; k++) if (+kids[k].dataset.idx === S.lb.i) { kids[k].scrollIntoView({ inline: "center", block: "nearest", behavior: "smooth" }); return; } }
  // Clicking an uncategorized image opens the whole 미분류 set in the lightbox so
  // you can flip through them all; a loose video (no thumb) opens its detail (plays).
  function fullImg(t) { return (t || "").replace(/&w=\d+$/, ""); }
  function openUncatLightbox(clicked) {
    if (!clicked.thumb || clicked.vid) { openPost(clicked.id); return; }  // videos play in their detail
    var list = filtered().filter(function (p) { return p.type === "uncat" && p.thumb && !p.vid; });
    var items = [], startIdx = 0;
    for (var i = 0; i < list.length; i++) {
      var p = list[i];
      if (p.id === clicked.id) startIdx = items.length;
      items.push({ url: fullImg(p.thumb), thumb: p.thumb, type: "image", post_title: p.title || "" });
    }
    openLightbox(items, startIdx);
  }
  /* ── AI chat (multi-turn, archive-grounded RAG; Gemini) ───────────────── */
  var CHAT_KEY = "ffs.chat.v1";
  function modelLabel(m) { return /flash/i.test(m) ? "빠름 (Flash)" : /pro/i.test(m) ? "정밀 (Pro)" : m; }
  function loadChat() { try { S.chat = JSON.parse(sessionStorage.getItem(CHAT_KEY) || "[]") || []; } catch (e) { S.chat = []; } }
  function saveChat() { try { sessionStorage.setItem(CHAT_KEY, JSON.stringify(S.chat.slice(-20))); } catch (e) { /* quota */ } }

  function renderChat() {
    els.main.innerHTML = "";
    var wrap = el("div", "fb-chat");
    var log = el("div", "fb-chat-log"); els.chatLog = log;
    if (!S.chat.length) {
      var hi = el("div", "fb-chat-hi");
      hi.appendChild(el("div", "h", "✦ 내 기록과 대화하기"));
      hi.appendChild(el("div", "p", "내 페이스북 기록을 근거로 답합니다. 사진·영상도 함께 찾아 보여줘요. 무엇이든 물어보세요."));
      var ex = el("div", "fb-chat-ex");
      ["내가 올린 여행 사진들 보여줘", "내가 가장 많이 쓴 주제는?", "2015년에 무슨 일이 있었지?"].forEach(function (q) {
        var b = el("button", "fb-chat-egg", q); b.onclick = function () { els.chatInput.value = q; sendChat(); };
        ex.appendChild(b);
      });
      hi.appendChild(ex); log.appendChild(hi);
    } else {
      S.chat.forEach(function (m) { log.appendChild(chatBubble(m)); });
    }
    wrap.appendChild(log);

    var comp = el("div", "fb-chat-composer");
    els.chatInput = el("textarea"); els.chatInput.placeholder = "메시지를 입력하세요…  (Enter 전송 · Shift+Enter 줄바꿈)"; els.chatInput.rows = 1;
    els.chatInput.addEventListener("input", function () { this.style.height = "auto"; this.style.height = Math.min(this.scrollHeight, 160) + "px"; });
    els.chatInput.addEventListener("keydown", function (e) { if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); sendChat(); } });
    els.chatSend = el("button", "fb-chat-send"); els.chatSend.innerHTML = "↑"; els.chatSend.title = "전송"; els.chatSend.onclick = sendChat;
    comp.appendChild(els.chatInput); comp.appendChild(els.chatSend);
    // model selector (Gemini flash ⇄ pro), persisted; sent with each chat turn.
    var models = CFG.models && CFG.models.length ? CFG.models : ["gemini-2.5-flash"];
    if (models.length > 1) {
      var msel = el("select", "fb-chat-model"); msel.title = "AI 모델";
      models.forEach(function (m) { msel.appendChild(new Option(modelLabel(m), m)); });
      msel.value = S.model; if (msel.value !== S.model) { S.model = msel.value; }
      msel.onchange = function () { S.model = msel.value; try { localStorage.setItem("ffs.model", S.model); } catch (e) {} };
      comp.appendChild(msel);
    }
    // agent (tool-use) toggle: when on, the AI searches + opens posts via tools
    // for grounded, per-item handling; off = the fast one-shot RAG path.
    var agt = el("button", "fb-chat-agent" + (S.agent ? " on" : ""), "🔧 도구");
    agt.title = "도구 사용(에이전트) — 기록을 직접 검색·열람해 더 정확히 답합니다";
    agt.onclick = function () { S.agent = !S.agent; try { localStorage.setItem("ffs.agent", S.agent ? "1" : "0"); } catch (e) {} agt.classList.toggle("on", S.agent); };
    comp.appendChild(agt);
    if (S.chat.length) { var clr = el("button", "fb-chat-clear", "대화 지우기"); clr.onclick = function () { S.chat = []; saveChat(); renderChat(); }; comp.appendChild(clr); }
    wrap.appendChild(comp);
    els.main.appendChild(wrap);
    scrollChat();
    setTimeout(function () { if (els.chatInput) els.chatInput.focus(); }, 30);
  }

  function chatBubble(m) {
    var b = el("div", "fb-chat-msg " + (m.role === "user" ? "me" : "bot"));
    var body = el("div", "fb-chat-body" + (m._pending ? " pending" : ""));
    if (m.role === "user") body.textContent = m.content;
    else if (m._pending) body.innerHTML = '<span class="fb-dot"></span><span class="fb-dot"></span><span class="fb-dot"></span>';
    else body.innerHTML = mdToHtml(m.content);
    b.appendChild(body);
    if (m.role === "bot" && !m._pending && m.media && m.media.length) {
      var media = m.media;
      // images the model already embedded inline → make them open the lightbox,
      // and EXCLUDE them from the gallery below so nothing shows up twice.
      var inlineSet = {};
      body.querySelectorAll("img.fb-md-img").forEach(function (im) {
        var src = im.getAttribute("src"); inlineSet[src] = 1;
        var idx = mediaIndex(media, src);
        if (idx >= 0) { im.style.cursor = "zoom-in"; im.onclick = function () { openLightbox(media, idx); }; }
      });
      var gmedia = media.filter(function (item) { return !inlineSet[item.url]; });
      var gal = el("div", "fb-chat-media");
      var PREV = 11;  // up to 12 tiles; the 12th is "+N" if there are more
      gmedia.slice(0, gmedia.length > 12 ? PREV : 12).forEach(function (item) {
        var cell = el("div", "fb-media-cell" + (item.type === "video" ? " vid" : ""));
        var im = el("img"); im.loading = "lazy"; im.src = item.url; im.alt = item.post_title || "";
        im.onerror = function () { cell.remove(); }; cell.appendChild(im);
        if (item.type === "video") cell.appendChild(el("span", "fb-media-play", "▶"));
        cell.onclick = function () { openLightbox(media, mediaIndex(media, item.url)); };
        gal.appendChild(cell);
      });
      if (gmedia.length > 12) {
        var more = el("div", "fb-media-cell fb-media-more"); more.appendChild(el("span", null, "+" + (gmedia.length - PREV)));
        more.onclick = function () { openLightbox(media, mediaIndex(media, gmedia[PREV].url)); };
        gal.appendChild(more);
      }
      if (gal.children.length) b.appendChild(gal);
    }
    if (m.role === "bot" && !m._pending && m.sources && m.sources.length) {
      var src = el("div", "fb-chat-src");
      src.appendChild(el("span", "fb-chat-src-h", "근거 글"));
      m.sources.forEach(function (s) { var p = S.byId[String(s.id)]; if (p) { var a = el("a", null, p.title || p.id); a.href = "#post/" + p.id; src.appendChild(a); } });
      b.appendChild(src);
    }
    if (m.role === "bot" && !m._pending) {
      var foot = el("div", "fb-chat-foot");
      var meta = [];
      if (m.model) meta.push(m.model);
      if (m.steps) meta.push("🔧 " + m.steps + "단계");
      if (m.ms) meta.push((m.ms / 1000).toFixed(1) + "초");
      foot.appendChild(el("div", "fb-chat-meta", meta.join("  ·  ")));
      var act = el("div", "fb-chat-act");
      var copy = el("button", "fb-chat-actbtn", "복사"); copy.title = "답변 복사";
      copy.onclick = function () { copyText(m.content); copy.textContent = "복사됨"; setTimeout(function () { copy.textContent = "복사"; }, 1200); };
      var regen = el("button", "fb-chat-actbtn", "다시"); regen.title = "다시 생성"; regen.onclick = function () { regenMessage(m); };
      var del = el("button", "fb-chat-actbtn del", "삭제"); del.title = "이 질문·답변 삭제"; del.onclick = function () { deleteMessage(m); };
      act.appendChild(copy); act.appendChild(regen); act.appendChild(del);
      foot.appendChild(act);
      b.appendChild(foot);
    }
    return b;
  }
  function copyText(t) { try { navigator.clipboard.writeText(t || ""); } catch (e) { /* no clipboard */ } }
  function deleteMessage(m) {
    var i = S.chat.indexOf(m); if (i < 0) return;
    var start = (i > 0 && S.chat[i - 1].role === "user") ? i - 1 : i;  // drop the Q + A pair
    S.chat.splice(start, i - start + 1);
    saveChat(); renderChat();
  }
  function regenMessage(m) {
    if (S.chatBusy) return;
    var i = S.chat.indexOf(m); if (i < 0) return;
    S.chat = S.chat.slice(0, i);  // drop this answer (+ anything after); last is the question
    if (!S.chat.length || S.chat[S.chat.length - 1].role !== "user") { renderChat(); return; }
    S.chat.push({ role: "bot", content: "", _pending: true });
    redrawChat(); sendRequest();
  }
  function scrollChat() { if (els.chatLog) els.chatLog.scrollTop = els.chatLog.scrollHeight; }
  function redrawChat() {
    if (!els.chatLog) { renderChat(); return; }
    els.chatLog.innerHTML = "";
    S.chat.forEach(function (m) { els.chatLog.appendChild(chatBubble(m)); });
    scrollChat();
  }

  function sendChat() {
    if (S.chatBusy || !els.chatInput) return;
    var text = (els.chatInput.value || "").trim();
    if (!text) return;
    els.chatInput.value = ""; els.chatInput.style.height = "auto";
    S.chat.push({ role: "user", content: text });
    S.chat.push({ role: "bot", content: "", _pending: true });
    redrawChat(); sendRequest();
  }
  // Sends the conversation and fills the trailing pending bot message. Shared by
  // sendChat (new turn) and regenMessage (re-ask the last question).
  function sendRequest() {
    var pending = S.chat[S.chat.length - 1];
    if (!pending || !pending._pending) return;
    S.chatBusy = true; if (els.chatSend) els.chatSend.disabled = true;
    var payload = S.chat.filter(function (m) { return !m._pending; })
      .map(function (m) { return { role: m.role === "user" ? "user" : "assistant", content: m.content }; }).slice(-12);
    var t0 = Date.now();
    fetch(CFG.chat, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ messages: payload, model: S.model, agent: S.agent }) })
      .then(function (r) { if (!r.ok) throw r.status; return r.json(); })
      .then(function (res) { pending._pending = false; pending.content = res.answer || "(응답 없음)"; pending.sources = res.sources || []; pending.media = res.media || []; pending.model = res.model || ""; pending.steps = res.steps || 0; pending.ms = Date.now() - t0; })
      .catch(function (err) { pending._pending = false; pending.content = (err === 429) ? "요청이 많아요. 잠시 후 다시 시도해 주세요." : "지금은 AI를 사용할 수 없어요. 잠시 후 다시 시도해 주세요."; })
      .then(function () { S.chatBusy = false; if (els.chatSend) els.chatSend.disabled = false; saveChat(); redrawChat(); });
  }

  /* tiny, safe markdown → HTML (escape first; then tables/headings/bold/italic/
     code/lists/blockquote/hr/links/paragraphs). No raw HTML survives except the
     model's own <br> inside cells, which we re-allow after escaping. */
  function mdEsc(s) { return s.replace(/[&<>"]/g, function (m) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[m]; }); }
  function mdInline(s) {
    return s.replace(/&lt;br\s*\/?&gt;/g, "<br>")
      .replace(/`([^`]+)`/g, function (_, c) { return "<code>" + c + "</code>"; })
      .replace(/!\[([^\]]*)\]\(((?:https?:|\/)[^)\s]+)\)/g, '<img class="fb-md-img" alt="$1" src="$2" loading="lazy">')
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/(^|[^*])\*([^*\n]+)\*/g, "$1<em>$2</em>")
      .replace(/\[([^\]]+)\]\((https?:[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  }
  function mdToHtml(text) {
    var lines = mdEsc(text || "").split("\n"), out = [], para = [], list = null;
    function flushP() { if (para.length) { out.push("<p>" + mdInline(para.join(" ")) + "</p>"); para = []; } }
    function flushL() { if (list) { out.push("<" + list.tag + ">" + list.items.map(function (x) { return "<li>" + mdInline(x) + "</li>"; }).join("") + "</" + list.tag + ">"); list = null; } }
    function flush() { flushP(); flushL(); }
    function cells(row) { return row.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map(function (c) { return c.trim(); }); }
    function isSep(s) { return /^[\s|:\-]+$/.test(s) && s.indexOf("-") >= 0; }
    for (var i = 0; i < lines.length; i++) {
      var t = lines[i].trim();
      if (!t) { flush(); continue; }
      // table: "| h | h |" followed by a "|---|---|" separator
      if (t.charAt(0) === "|" && i + 1 < lines.length && isSep(lines[i + 1].trim())) {
        flush();
        var head = cells(t); i++;
        var rows = [];
        while (i + 1 < lines.length && lines[i + 1].trim().charAt(0) === "|") { i++; rows.push(cells(lines[i])); }
        var h = '<div class="fb-tw"><table><thead><tr>' + head.map(function (c) { return "<th>" + mdInline(c) + "</th>"; }).join("") + "</tr></thead><tbody>";
        rows.forEach(function (r) { h += "<tr>" + r.map(function (c) { return "<td>" + mdInline(c) + "</td>"; }).join("") + "</tr>"; });
        out.push(h + "</tbody></table></div>");
        continue;
      }
      var hm = t.match(/^(#{1,4})\s+(.*)$/);
      if (hm) { flush(); var lv = Math.min(hm[1].length + 2, 6); out.push("<h" + lv + ">" + mdInline(hm[2]) + "</h" + lv + ">"); continue; }
      if (/^([-*_])\1{2,}$/.test(t)) { flush(); out.push("<hr>"); continue; }
      if (/^>\s?/.test(t)) {  // collect consecutive blockquote lines into one
        flush();
        var bq = [];
        while (i < lines.length && /^>\s?/.test(lines[i].trim())) { bq.push(lines[i].trim().replace(/^>\s?/, "")); i++; }
        i--;
        out.push("<blockquote>" + bq.map(mdInline).join("<br>") + "</blockquote>");
        continue;
      }
      var um = t.match(/^[-*]\s+(.*)$/), om = t.match(/^\d+[.)]\s+(.*)$/);
      if (um || om) { flushP(); var tag = um ? "ul" : "ol"; if (!list || list.tag !== tag) { flushL(); list = { tag: tag, items: [] }; } list.items.push((um || om)[1]); continue; }
      flushL(); para.push(t);
    }
    flush();
    return out.join("");
  }
})();
