/* FreedomFromSNS — local Facebook-archive browser. Pure vanilla, no framework.
 * Everything (browse, calendar, filters, text search) renders client-side from
 * /api/index, so it's instant. Post detail lazy-loads from /api/fb/objects.
 * Semantic search (/api/search) and the AI chat (/api/chat) are Gemini-backed,
 * local-only — no Weft, no apicascade, no cloud middleman.
 */
(function () {
  "use strict";
  var CFG = window.FFS || {};
  var PAGE = 60;
  // Brand logo: index 0 is the typographic wordmark (null); the rest are emblems
  // the server auto-discovers from viewer/logo-candidates/ (sorted; mtime-busted).
  // Clicking the brand goes Home AND rotates to the next design (persisted).
  var LOGOS = [null].concat((CFG.logos && CFG.logos.length) ? CFG.logos
    : ["/static/logo-candidates/01-monogram.png", "/static/logo-candidates/02-bird.png", "/static/logo-candidates/03-unplug.png"]);

  /* ── i18n (KO / EN) ──────────────────────────────────────────────────── */
  var I18N = {
    ko: {
      archive: "아카이브", browse: "둘러보기", calendar: "달력", aichat: "✦ AI 대화",
      search_ph: "검색…", all: "전체", year_all: "모든 연도", load_fail: "콘텐츠를 불러오지 못했습니다.",
      type_photo: "사진", type_video: "영상", type_link: "링크", type_status: "글", type_share: "공유", type_uncat: "미분류", type_trash: "휴지통",
      sel_start: "선택", sel_done: "완료", sel_all: "전체 선택", sel_none: "선택 해제", sel_count: "개 선택됨", sel_erase: "삭제", sel_restore: "복원",
      show_hidden: "숨김 보기", show_hidden_hint: "삭제(숨김) 처리한 글을 함께 보여줍니다 — 데이터는 지워지지 않고 태그만 붙습니다",
      theme: "테마",
      mon: "일월화수목금토", months: "1월 2월 3월 4월 5월 6월 7월 8월 9월 10월 11월 12월",
      related_searching: "  ·  관련 글 찾는 중…", semantic: "  ·  의미 검색",
      searching: "검색 중…", no_results: "결과가 없습니다.", no_results2: "결과 없음",
      close: "닫기", view_original: "원문 보기 ↗", loading: "불러오는 중…", prev: "이전", next: "다음",
      public: "공개", private: "비공개", privacy_hint: "공개 설정 — 비공개 글은 공유·내보내기에서 제외됩니다 (내 컴퓨터에서는 계속 보입니다)",
      jump_latest: "최신으로 ↓",
      load_body_fail: "본문을 불러올 수 없습니다.", related: "관련 글", link_preview: "링크 미리보기…",
      source_fallback: "원본", lb_goto: "위치로 이동", original_short: "원문 ↗", untitled: "(무제)", lb_expand: "전체화면으로 보기",
      chat_hi: "✦ 내 기록과 대화하기",
      chat_sub: "내 페이스북 기록을 근거로 답합니다. 사진·영상도 함께 찾아 보여줘요. 무엇이든 물어보세요.",
      chat_eg1: "내가 올린 여행 사진들 보여줘", chat_eg2: "내가 가장 많이 쓴 주제는?", chat_eg3: "2015년에 무슨 일이 있었지?",
      chat_ph: "메시지를 입력하세요…  (Enter 전송 · Shift+Enter 줄바꿈)",
      send: "전송", ai_model: "AI 모델", model_fast: "빠름", model_precise: "정밀 (사고)",
      settings: "설정", set_chat: "AI 대화 (채팅 모델)", set_chat_hint: "보유한 AI를 연결하세요 — 무료 키, 유료 키, 또는 로컬 모델.",
      set_provider: "제공자", set_fast: "빠름 모델", set_precise: "정밀 모델", set_key: "API 키",
      set_key_set: "(키 설정됨 — 바꾸려면 새로 입력)", set_key_ph: "API 키를 붙여넣으세요", set_get_key: "키 발급:", set_no_key: "키가 필요 없습니다 (로컬).",
      set_test: "연결 테스트", set_testing: "테스트 중…", set_embed: "의미 검색 (임베딩)",
      set_embed_hint: "검색·대화의 근거가 되는 임베딩 제공자입니다. Gemini 무료 키를 권장합니다 (다운로드 없음); 키 없이 로컬(오프라인)도 가능합니다.",
      set_model: "모델", set_embed_note: "임베딩을 바꾸면 다시 만들어야 합니다: 터미널에서 `ffs embed` 실행.",
      set_save: "저장", set_saving: "저장 중…", set_saved: "저장됨 ✓ — 새로고침합니다", set_err: "오류가 발생했습니다.",
      tools: "🔧 도구", tools_title: "도구 사용(에이전트) — 기록을 직접 검색·열람해 더 정확히 답합니다",
      clear_chat: "대화 지우기", sources: "근거 글",
      copy: "복사", copied: "복사됨", copy_title: "답변 복사", regen: "다시", regen_title: "다시 생성",
      del: "삭제", del_title: "이 질문·답변 삭제", no_response: "(응답 없음)",
      err_busy: "요청이 많아요. 잠시 후 다시 시도해 주세요.", err_unavailable: "지금은 AI를 사용할 수 없어요. 잠시 후 다시 시도해 주세요.",
    },
    en: {
      archive: "Archive", browse: "Browse", calendar: "Calendar", aichat: "✦ AI Chat",
      search_ph: "Search…", all: "All", year_all: "All years", load_fail: "Couldn't load content.",
      type_photo: "Photos", type_video: "Videos", type_link: "Links", type_status: "Text", type_share: "Shares", type_uncat: "Unsorted", type_trash: "Trash",
      sel_start: "Select", sel_done: "Done", sel_all: "Select all", sel_none: "Clear", sel_count: " selected", sel_erase: "Erase", sel_restore: "Restore",
      show_hidden: "Show hidden", show_hidden_hint: "Also show erased (hidden) posts — nothing is deleted, just tagged",
      theme: "Theme",
      mon: "SMTWTFS", months: "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec",
      related_searching: "  ·  finding related…", semantic: "  ·  semantic",
      searching: "Searching…", no_results: "No results.", no_results2: "No results",
      close: "Close", view_original: "View original ↗", loading: "Loading…", prev: "Previous", next: "Next",
      public: "Public", private: "Private", privacy_hint: "Privacy — private posts are excluded from sharing/export (still visible on your computer)",
      jump_latest: "Jump to latest ↓",
      load_body_fail: "Couldn't load the post.", related: "Related", link_preview: "Link preview…",
      source_fallback: "Source", lb_goto: "Jump to position", original_short: "Original ↗", untitled: "(untitled)", lb_expand: "View full screen",
      chat_hi: "✦ Chat with my archive",
      chat_sub: "Answers grounded in your Facebook archive — it finds your photos and videos too. Ask anything.",
      chat_eg1: "Show my travel photos", chat_eg2: "What did I write about most?", chat_eg3: "What happened in 2015?",
      chat_ph: "Type a message…  (Enter to send · Shift+Enter for a new line)",
      send: "Send", ai_model: "AI model", model_fast: "Fast", model_precise: "Precise (thinking)",
      settings: "Settings", set_chat: "AI chat (chat model)", set_chat_hint: "Connect any AI you have — a free key, a paid key, or a local model.",
      set_provider: "Provider", set_fast: "Fast model", set_precise: "Precise model", set_key: "API key",
      set_key_set: "(key set — type a new one to change)", set_key_ph: "Paste your API key", set_get_key: "Get a key:", set_no_key: "No key needed (local).",
      set_test: "Test connection", set_testing: "Testing…", set_embed: "Semantic search (embeddings)",
      set_embed_hint: "The embedding provider behind search + chat grounding. A free Gemini key is recommended (no download); fully offline local works with no key.",
      set_model: "Model", set_embed_note: "Changing embeddings needs a rebuild: run `ffs embed` in a terminal.",
      set_save: "Save", set_saving: "Saving…", set_saved: "Saved ✓ — reloading", set_err: "Something went wrong.",
      tools: "🔧 Tools", tools_title: "Agent mode — searches and opens your posts directly for more accurate answers",
      clear_chat: "Clear chat", sources: "Sources",
      copy: "Copy", copied: "Copied", copy_title: "Copy answer", regen: "Retry", regen_title: "Regenerate",
      del: "Delete", del_title: "Delete this Q&A", no_response: "(no response)",
      err_busy: "Too many requests. Please try again shortly.", err_unavailable: "AI is unavailable right now. Please try again shortly.",
    },
  };
  function tr(k) { var d = I18N[S.lang] || I18N.ko; return k in d ? d[k] : (I18N.ko[k] != null ? I18N.ko[k] : k); }
  function typeLabel(t) { return tr("type_" + t) || tr("type_status"); }
  var EN = function () { return S.lang === "en"; };
  function countN(n) { return n.toLocaleString() + (EN() ? "" : "개"); }
  function yearN(y) { return EN() ? "" + y : y + "년"; }
  function moreN(n) { return EN() ? "+" + n + " more" : "+" + n + " 더보기"; }
  function ymTitle(y, m) { return EN() ? tr("months").split(" ")[m - 1] + " " + y : y + "년 " + m + "월"; }

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
    ctx: null,                  // ordered post ids for detail prev/next (current context)
    ctxMedia: null,             // {key, p:Promise<{list,byUrl}>} — category-wide media for the lightbox
    selMode: false, sel: {}, selAnchor: null,   // multi-select: mode, {id:true}, range anchor
    logo: (function () { try { return parseInt(localStorage.getItem("ffs.logo"), 10) || 0; } catch (e) { return 0; } })(),
    theme: (function () { try { return parseInt(localStorage.getItem("ffs.theme"), 10) || 0; } catch (e) { return 0; } })(),
    showErased: (function () { try { return localStorage.getItem("ffs.showErased") === "1"; } catch (e) { return false; } })(),
    scroll: (function () { try { return JSON.parse(localStorage.getItem("ffs.scroll") || "{}") || {}; } catch (e) { return {}; } })(),
    _rendered: null,            // last view actually rendered (for enter-restore)
    lang: (function () { try { return localStorage.getItem("ffs.lang") || (/^en/i.test(navigator.language || "") ? "en" : "ko"); } catch (e) { return "ko"; } })(),
    model: (function () { try { return localStorage.getItem("ffs.model") || (CFG.defaultModel || "gemini-2.5-flash"); } catch (e) { return CFG.defaultModel || "gemini-2.5-flash"; } })(),
    agent: (function () { try { var v = localStorage.getItem("ffs.agent"); return v === null ? true : v === "1"; } catch (e) { return true; } })(),
  };
  var els = {};

  /* ── boot ───────────────────────────────────────────────────────────── */
  function el(t, c, txt) { var e = document.createElement(t); if (c) e.className = c; if (txt != null) e.textContent = txt; return e; }
  function fmtDate(d) { return d ? d.slice(0, 10) : ""; }

  /* ── theme system: a theme is a token set (viewer/themes/*.json) applied as
     :root custom properties. The whole stylesheet flows from those tokens, so
     one file repaints everything. Reset-then-apply lets a theme be partial
     (only the tokens it overrides; the rest fall back to the CSS :root). ───── */
  function THEMES() { return (CFG.themes && CFG.themes.length) ? CFG.themes : [{ name: "Gold Noir", tokens: {} }]; }
  function applyTheme(tokens) {
    var st = document.documentElement.style;
    for (var i = st.length - 1; i >= 0; i--) { var p = st[i]; if (p.indexOf("--") === 0) st.removeProperty(p); }
    if (tokens) for (var k in tokens) st.setProperty(k.charAt(0) === "-" ? k : "--" + k, tokens[k]);
  }
  function setTheme(i) {
    var t = THEMES();
    S.theme = ((i % t.length) + t.length) % t.length;
    try { localStorage.setItem("ffs.theme", String(S.theme)); } catch (e) {}
    applyTheme(t[S.theme].tokens);
    if (els.themeBtn) els.themeBtn.title = tr("theme") + ": " + t[S.theme].name;
  }
  // Theme picker popover — a swatch + name per theme (too many to blind-cycle).
  function openThemeMenu(anchor) {
    if (!els.themeMenu) {
      els.themeMenu = el("div", "fb-theme-menu");
      document.body.appendChild(els.themeMenu);
      document.addEventListener("click", closeThemeMenu);
      document.addEventListener("keydown", function (e) { if (e.key === "Escape") closeThemeMenu(); });
    }
    var t = THEMES();
    els.themeMenu.innerHTML = "";
    t.forEach(function (th, i) {
      var row = el("button", "fb-theme-row" + (i === S.theme ? " on" : ""));
      var sw = el("span", "fb-theme-sw"); sw.style.background = (th.tokens && (th.tokens.gold || th.tokens.accent)) || "var(--gold)";
      row.appendChild(sw); row.appendChild(el("span", "fb-theme-name", th.name));
      row.onclick = function (e) { e.stopPropagation(); setTheme(i); closeThemeMenu(); };
      els.themeMenu.appendChild(row);
    });
    var r = anchor.getBoundingClientRect();
    els.themeMenu.style.top = (r.bottom + 6) + "px";
    els.themeMenu.style.right = Math.max(8, window.innerWidth - r.right) + "px";
    els.themeMenu.classList.add("on");
  }
  function closeThemeMenu() { if (els.themeMenu) els.themeMenu.classList.remove("on"); }
  function toggleThemeMenu(a) { (els.themeMenu && els.themeMenu.classList.contains("on")) ? closeThemeMenu() : openThemeMenu(a); }
  // Brand wordmark: FreedomFromSNS with the F · F · S (Freedom · From · SNS)
  // picked out as accents — the "FFS" reads out of the full name.
  function brandWordmark() {
    return '<span class="fa">F</span>reedom<span class="fa">F</span>rom<span class="fa">S</span>NS';
  }
  // Render the current logo into the brand. The wordmark variant is the big
  // lettering; an emblem variant pairs the icon with the same wordmark, smaller
  // and less prominent, so the name still reads next to the graphic.
  function renderBrand(brand) {
    var src = LOGOS[S.logo % LOGOS.length];
    brand.classList.toggle("img", !!src);
    brand.innerHTML = src
      ? ('<img class="fb-logo-img" src="' + src + '" alt="FreedomFromSNS"><span class="fb-logo-text">' + brandWordmark() + '</span>')
      : brandWordmark();
  }

  fetch(CFG.index).then(function (r) { return r.json(); }).then(function (data) {
    S.posts = (data || []).filter(function (p) { return p.date; });
    S.posts.forEach(function (p) { S.byId[p.id] = p; });
    var latest = S.posts.length ? S.posts[0].date : "";
    S.cal = latest ? { y: +latest.slice(0, 4), m: +latest.slice(5, 7) } : { y: new Date().getFullYear(), m: 1 };
    if (CFG.related) fetch(CFG.related).then(function (r) { return r.json(); }).then(function (rel) { S.related = rel || {}; }).catch(function () {});
    loadChat();
    // remember the last place: with no hash, reopen the last view the user left.
    if (!location.hash) {
      var lastView = ""; try { lastView = localStorage.getItem("ffs.view") || ""; } catch (e) {}
      if (lastView === "calendar" || (lastView === "chat" && CFG.chat)) history.replaceState(null, "", "#" + lastView);
    }
    routeFromHash();
    window.addEventListener("hashchange", routeFromHash);
    installScrollPersistence();
  }).catch(function () { els.main.innerHTML = '<div class="fb-empty">' + tr("load_fail") + '</div>'; });

  /* ── chrome (header + filters) built once ───────────────────────────── */
  function buildChrome() {
    var top = el("div", "fb-top");
    var bar = el("div", "fb-bar");
    var brand = el("div", "fb-brand"); renderBrand(brand);
    brand.style.cursor = "pointer"; brand.title = "FreedomFromSNS";
    brand.onclick = function () {   // go Home AND rotate to the next logo design
      S.logo = (S.logo + 1) % LOGOS.length;
      try { localStorage.setItem("ffs.logo", String(S.logo)); } catch (e) {}
      renderBrand(brand);
      goHome();
    };

    var tabs = el("div", "fb-tabs");
    els.tabBrowse = el("button", "fb-tab", tr("browse")); els.tabBrowse.onclick = goHome;
    els.tabCal = el("button", "fb-tab", tr("calendar")); els.tabCal.onclick = function () { location.hash = "#calendar" + (S.q ? "=" + encodeURIComponent(S.q) : ""); };
    tabs.appendChild(els.tabBrowse); tabs.appendChild(els.tabCal);
    if (CFG.chat) {
      els.tabChat = el("button", "fb-tab fb-tab-ai", tr("aichat")); els.tabChat.onclick = function () { location.hash = "#chat"; };
      tabs.appendChild(els.tabChat);
    }

    // Unified search: typing filters instantly by keyword, then auto-enriches
    // with semantic results (페르시아→이란) when the box answers. No Enter needed.
    var search = el("div", "fb-search");
    search.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/></svg>';
    els.q = el("input"); els.q.type = "search"; els.q.placeholder = tr("search_ph");
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

  // The filter bar persists across all views (browse / calendar / chat) so the menu
  // never vanishes. Content-type chips + count show on browse & calendar; the year
  // dropdown is browse-only (the calendar's own year sidebar makes it redundant);
  // chat carries only the global language toggle. The flag sits at the right edge.
  function renderFilters() {
    els.filters.innerHTML = "";
    els.count = null;
    if (S.view !== "chat" && S.view !== "settings") {
      // Two groups: shown-by-default content, then a divider, then "click-into"
      // buckets (링크/공유/미분류) that are hidden from 전체 — you open them on demand.
      function chip(t, sec) {
        var c = el("button", "fb-chip" + (sec ? " sec" : "") + (S.type === t ? " on" : ""), t === "all" ? tr("all") : typeLabel(t));
        c.dataset.t = t; c.onclick = function () { S.type = t; S.shown = PAGE; renderCurrentView(); };
        return c;
      }
      ["all", "photo", "video", "status"].forEach(function (t) { els.filters.appendChild(chip(t, false)); });
      els.filters.appendChild(el("div", "fb-chip-div"));
      ["link", "share", "uncat"].forEach(function (t) { els.filters.appendChild(chip(t, true)); });
    }
    els.filters.appendChild(el("div", "fb-sp"));
    if (S.view === "browse") {           // reveal erased ("hidden") items inline, tagged
      var hb = el("button", "fb-selbtn" + (S.showErased ? " on" : ""), "👁 " + tr("show_hidden"));
      hb.title = tr("show_hidden_hint");
      hb.onclick = function () { S.showErased = !S.showErased; try { localStorage.setItem("ffs.showErased", S.showErased ? "1" : "0"); } catch (e) {} S.shown = PAGE; renderCurrentView(); };
      els.filters.appendChild(hb);
    }
    if (S.view === "browse") {           // year dropdown only on browse (calendar has its sidebar)
      var sel = el("select", "fb-year");
      sel.appendChild(new Option(tr("year_all"), "all"));
      uniqueYears().forEach(function (y) { sel.appendChild(new Option(yearN(y), y)); });
      sel.value = S.year; sel.onchange = function () { S.year = sel.value; S.shown = PAGE; renderCurrentView(); };
      els.filters.appendChild(sel);
    }
    if (S.view === "browse") {           // multi-select toggle (manage many posts at once)
      var selBtn = el("button", "fb-selbtn" + (S.selMode ? " on" : ""), S.selMode ? tr("sel_done") : tr("sel_start"));
      selBtn.onclick = toggleSelMode;
      els.filters.appendChild(selBtn);
    }
    if (S.view !== "chat" && S.view !== "settings") { els.count = el("div", "fb-count"); els.filters.appendChild(els.count); }
    var gear = el("button", "fb-theme" + (S.view === "settings" ? " on" : ""), "⚙"); gear.title = tr("settings");
    gear.onclick = function () { location.hash = "#settings"; };
    els.filters.appendChild(gear);
    // theme cycler — instant repaint via :root tokens (a swatch of the accent)
    var themeBtn = el("button", "fb-theme"); els.themeBtn = themeBtn;
    themeBtn.title = tr("theme") + ": " + THEMES()[S.theme % THEMES().length].name;
    themeBtn.innerHTML = '🎨';
    themeBtn.onclick = function (e) { e.stopPropagation(); toggleThemeMenu(themeBtn); };
    els.filters.appendChild(themeBtn);
    var lang = el("button", "fb-lang", EN() ? "🇰🇷 한국어" : "🇺🇸 English");
    lang.title = EN() ? "한국어로 전환" : "Switch to English";
    lang.onclick = function () { setLang(EN() ? "ko" : "en"); };
    els.filters.appendChild(lang);
  }

  // Switch UI language in place: persist, re-label the once-built chrome, re-render.
  function setLang(lang) {
    S.lang = lang;
    try { localStorage.setItem("ffs.lang", lang); } catch (e) {}
    document.documentElement.lang = lang;
    if (els.tabBrowse) els.tabBrowse.textContent = tr("browse");
    if (els.tabCal) els.tabCal.textContent = tr("calendar");
    if (els.tabChat) els.tabChat.textContent = tr("aichat");
    if (els.q) els.q.placeholder = tr("search_ph");
    renderCurrentView();
  }

  function uniqueYears() { var s = {}; S.posts.forEach(function (p) { s[p.date.slice(0, 4)] = 1; }); return Object.keys(s).sort().reverse(); }
  // length-based text fit for text-only cards (a cheap stand-in for a measured
  // pretext fit — no per-card reflow): short → large + filling, long → compact.
  function fitFont(len) { return len < 40 ? "1.5rem" : len < 90 ? "1.2rem" : len < 170 ? "1.05rem" : len < 280 ? ".92rem" : ".85rem"; }

  /* ── scroll / last-place restore ────────────────────────────────────────
     Browse + calendar scroll the window; chat scrolls its own log. Each view's
     position is remembered (localStorage) and restored when you return — chat
     especially, which lands back where you left the conversation. */
  var BOTTOM = -1;  // sentinel: stick to the bottom (chat default)
  function winEl() { return document.scrollingElement || document.documentElement; }
  function isChatBottom() { var e = els.chatLog; return !e || (e.scrollHeight - e.scrollTop - e.clientHeight) < 80; }
  function persistScroll() { try { localStorage.setItem("ffs.scroll", JSON.stringify(S.scroll)); } catch (e) {} }
  function saveScroll() {
    if (S.view === "chat") { if (els.chatLog) S.scroll.chat = isChatBottom() ? BOTTOM : els.chatLog.scrollTop; }
    else { S.scroll[S.view] = winEl().scrollTop; }
    persistScroll();
  }
  function restoreChatScroll() {
    if (!els.chatLog) return;
    var s = S.scroll.chat;
    if (s == null || s === BOTTOM) scrollChat(); else els.chatLog.scrollTop = s;
    updateChatPill();
  }
  function restoreWinScroll() {
    var s = S.scroll[S.view];
    winEl().scrollTop = (typeof s === "number" && s > 0) ? s : 0;
  }
  var _scrollDeb;
  function installScrollPersistence() {
    window.addEventListener("scroll", function () {
      if (S.view === "chat") return;          // chat persists via its log listener
      clearTimeout(_scrollDeb); _scrollDeb = setTimeout(saveScroll, 200);
    }, { passive: true });
    window.addEventListener("beforeunload", saveScroll);
    document.addEventListener("visibilitychange", function () { if (document.visibilityState === "hidden") saveScroll(); });
  }
  function updateChatPill() { if (els.chatPill) els.chatPill.classList.toggle("on", !isChatBottom()); }
  function anchorLastUser() {              // ChatGPT-style: new question rides to the top
    if (!els.chatLog) return;
    var me = els.chatLog.querySelectorAll(".fb-chat-msg.me");
    var last = me[me.length - 1];
    if (last) els.chatLog.scrollTop = Math.max(0, last.offsetTop - 12); else scrollChat();
    updateChatPill();
  }

  /* ── routing ────────────────────────────────────────────────────────── */
  //  Hash forms: #browse | #calendar | #chat | #post/<id> | #<view>=<query>.
  //  The search query lives in the URL so it's restorable + back/forward-safe;
  //  doSearch updates it with replaceState (no history pile-up per keystroke).
  function renderCurrentView() {
    var entering = S.view !== S._rendered;
    renderFilters();                     // bar persists across all views
    if (S.view === "calendar") renderCalendar();
    else if (S.view === "chat") renderChat();   // chat self-restores its log scroll
    else if (S.view === "settings") renderSettings();
    else renderBrowse();
    if (entering) {
      S._rendered = S.view;
      try { localStorage.setItem("ffs.view", S.view); } catch (e) {}
      if (S.view !== "chat") requestAnimationFrame(restoreWinScroll);
    }
    if (els.selBar) updateSelBar();   // hide the select bar when leaving browse
  }
  function routeFromHash() {
    if (!els.main) buildChrome();
    var h = location.hash.slice(1);
    if (h.indexOf("post/") === 0) { var pid = h.slice(5); try { pid = decodeURIComponent(pid); } catch (e) {} openDetail(pid); return; }
    closeModal();
    var eq = h.indexOf("="), view = eq >= 0 ? h.slice(0, eq) : h;
    var q = "";
    if (eq >= 0) { try { q = decodeURIComponent(h.slice(eq + 1)); } catch (e) { q = h.slice(eq + 1); } }
    var nextView = (view === "calendar") ? "calendar" : (view === "settings") ? "settings"
      : (view === "chat" && CFG.chat) ? "chat" : "browse";
    if (nextView !== S.view) saveScroll();   // remember where we were before leaving
    S.view = nextView;
    els.tabBrowse.classList.toggle("on", S.view === "browse");
    els.tabCal.classList.toggle("on", S.view === "calendar");
    if (els.tabChat) els.tabChat.classList.toggle("on", S.view === "chat");
    // settings/chat carry no query — leave the search bar untouched in them.
    if (S.view !== "chat" && S.view !== "settings" && q !== S.q) {
      S.q = q; S.semanticIds = null; S.shown = PAGE; var token = ++S.searchToken;
      if (els.q) els.q.value = q;
      if (q && q.length >= 2 && CFG.search) { S.semanticLoading = true; fireSemantic(q, token); }
      else S.semanticLoading = false;
    }
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
    renderCurrentView();
  }

  /* ── browse grid (filter + paginate, instant) ───────────────────────── */
  function baseList() {
    if (S.semanticIds) return S.semanticIds.map(function (id) { return S.byId[id]; }).filter(Boolean);
    var q = S.q.toLowerCase();
    return S.posts.filter(function (p) { return !q || (p.title + " " + (p.excerpt || "")).toLowerCase().indexOf(q) >= 0; });
  }
  var BUCKETS = { link: 1, share: 1, uncat: 1 };  // click-into; hidden from 전체
  function passType(p) {
    if (p.erased && !S.showErased) return false;               // erased = a hidden tag; reveal with the toggle
    if (S.type === "all") return !BUCKETS[p.type] && !p.empty;  // default feed: real content only
    if (BUCKETS[S.type]) return p.type === S.type;              // a bucket shows its whole type
    return p.type === S.type && !p.empty;                       // 사진/영상/글: hide empties too
  }
  function passYear(p) { return S.year === "all" || p.date.slice(0, 4) === S.year; }
  function filtered() {
    return baseList().filter(function (p) { return passType(p) && passYear(p); });
  }

  /* ── multi-select: manage many posts at once (privacy / soft-erase) ──────────
     Works on browse AND search results (the same grid). Click toggles; Shift+
     click range-selects in the displayed order; select-all / clear for groups.
     A sticky bar drives bulk actions. Nothing is deleted — erase is a mark. */
  function selCount() { return Object.keys(S.sel).length; }
  function selectedFbids() {
    return Object.keys(S.sel).map(function (id) { return S.byId[id] && S.byId[id].fbid; }).filter(Boolean);
  }
  function toggleSelMode() {
    S.selMode = !S.selMode;
    if (!S.selMode) { S.sel = {}; S.selAnchor = null; }
    renderCurrentView();
  }
  function toggleSelect(p, e) {
    if (e && e.shiftKey && S.selAnchor != null) {     // range: anchor → clicked, in display order
      var ids = filtered().map(function (x) { return x.id; });
      var a = ids.indexOf(S.selAnchor), b = ids.indexOf(p.id);
      if (a >= 0 && b >= 0) { for (var i = Math.min(a, b); i <= Math.max(a, b); i++) S.sel[ids[i]] = true; }
    } else {
      if (S.sel[p.id]) delete S.sel[p.id]; else S.sel[p.id] = true;
      S.selAnchor = p.id;
    }
    updateSelectionUI();
  }
  function selectAll() { filtered().forEach(function (p) { S.sel[p.id] = true; }); updateSelectionUI(); }
  function deselectAll() { S.sel = {}; S.selAnchor = null; updateSelectionUI(); }
  function refreshCards() {     // sync the .sel class on rendered cards (no full re-render)
    if (!els.grid) return;
    var kids = els.grid.children;
    for (var i = 0; i < kids.length; i++) { var id = kids[i].dataset.id; if (id) kids[i].classList.toggle("sel", !!S.sel[id]); }
  }
  function updateSelectionUI() { refreshCards(); updateSelBar(); }

  function buildSelBar() {
    els.selBar = el("div", "fb-selbar");
    els.selCount = el("div", "fb-selbar-n");
    var all = el("button", "fb-selbar-btn", tr("sel_all")); all.onclick = selectAll;
    var none = el("button", "fb-selbar-btn", tr("sel_none")); none.onclick = deselectAll;
    els.selPublic = el("button", "fb-selbar-btn", "🌐 " + tr("public")); els.selPublic.onclick = function () { bulkPrivacy("public"); };
    els.selPrivate = el("button", "fb-selbar-btn", "🔒 " + tr("private")); els.selPrivate.onclick = function () { bulkPrivacy("private"); };
    els.selErase = el("button", "fb-selbar-btn danger", "🗑 " + tr("sel_erase")); els.selErase.onclick = function () { bulkErase(true); };
    els.selRestore = el("button", "fb-selbar-btn", "♻ " + tr("sel_restore")); els.selRestore.onclick = function () { bulkErase(false); };
    var done = el("button", "fb-selbar-btn done", tr("sel_done")); done.onclick = toggleSelMode;
    [els.selCount, all, none, els.selPublic, els.selPrivate, els.selErase, els.selRestore, done].forEach(function (x) { els.selBar.appendChild(x); });
    document.body.appendChild(els.selBar);
  }
  function updateSelBar() {
    if (!els.selBar) buildSelBar();
    var n = selCount();
    els.selBar.classList.toggle("on", S.selMode && S.view === "browse");
    els.selCount.textContent = n + tr("sel_count");
    els.selRestore.style.display = S.showErased ? "" : "none";   // restore only when erased items are visible
    [els.selPublic, els.selPrivate, els.selErase, els.selRestore].forEach(function (b) { b.disabled = n === 0; });
  }
  function bulkPrivacy(privacy) {
    var fbids = selectedFbids(); if (!fbids.length) return;
    fetch("/api/privacy", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ fbids: fbids, privacy: privacy }) })
      .then(function (r) { return r.json(); }).then(function () {
        var priv = privacy !== "public";
        Object.keys(S.sel).forEach(function (id) { if (S.byId[id]) S.byId[id].private = priv; });
        renderCurrentView();
      }).catch(function () {});
  }
  function bulkErase(erased) {
    var fbids = selectedFbids(); if (!fbids.length) return;
    fetch("/api/erase", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ fbids: fbids, erased: erased }) })
      .then(function (r) { return r.json(); }).then(function () {
        Object.keys(S.sel).forEach(function (id) { if (S.byId[id]) S.byId[id].erased = erased; });
        S.sel = {}; S.selAnchor = null;
        renderCurrentView();   // erased items vanish (unless "show hidden"); restored ones lose the tag
      }).catch(function () {});
  }

  function card(p) {
    // Clicking a card opens its detail, carrying the CURRENT context (the filtered
    // list as shown — 전체 or 사진/영상/글/etc) so prev/next walks every item in it,
    // regardless of type. The detail's own image zoom still uses the lightbox strip.
    var c = el("div", "fb-card" + (S.selMode && S.sel[p.id] ? " sel" : "")); c.dataset.id = p.id;
    c.onclick = function (e) {
      if (S.selMode) { e.preventDefault(); toggleSelect(p, e); return; }  // select instead of open
      openPost(p.id, contextIds());
    };
    if (S.selMode) c.appendChild(el("div", "fb-check"));   // checkbox overlay
    if (p.private) { var lk = el("div", "fb-lock", "🔒"); lk.title = tr("privacy_hint"); c.appendChild(lk); }
    if (p.erased) c.appendChild(el("div", "fb-erased-tag", "🗑"));
    var isLink = p.type === "link" && p.link_url;
    var hasImage = !!p.thumb;
    var preview = (p.preview || p.excerpt || "").trim();
    var hasText = !!preview;
    var thumb = null, body = null, textEl = null;

    // Reactive: whichever element is present takes the space. An image with no text
    // FILLS the whole card; text with no image fills the card; with both, the image
    // sits on top (fixed ratio) and the text below — no empty placeholder boxes.
    if (hasImage || isLink) {
      var fill = hasImage && !hasText && !isLink;   // image-only → let it fill
      thumb = el("div", "fb-thumb" + (hasImage ? "" : " ph") + (fill ? " fill" : ""));
      if (hasImage) {
        var im = el("img"); im.loading = "lazy"; im.src = p.thumb;
        im.onerror = function () { thumb.classList.add("ph"); thumb.dataset.ic = p.vid ? "▶" : "▦"; im.remove(); };
        thumb.appendChild(im);
        if (p.vid) thumb.appendChild(el("span", "fb-thumb-play", "▶"));
      } else { thumb.dataset.ic = "🔗"; }                 // link awaiting its preview
      thumb.appendChild(el("div", "fb-badge " + p.type, typeLabel(p.type)));
      if (fill) thumb.appendChild(el("div", "fb-thumb-date", fmtDate(p.date)));
      c.appendChild(thumb);
    } else {
      c.classList.add("fb-card-text");                    // no visual → text takes over
      c.appendChild(el("div", "fb-badge " + p.type + " float", typeLabel(p.type)));
    }
    if (hasText || isLink || !hasImage) {
      body = el("div", "fb-body");
      body.appendChild(el("div", "fb-date", fmtDate(p.date)));
      textEl = el("div", "fb-text", preview || (!hasImage ? (p.title || tr("untitled")) : ""));
      // pretext-style fit (cheap, length-based): on a text-only card, a short post
      // reads large and fills the card; a long one shrinks so more of it fits.
      if (!hasImage) textEl.style.fontSize = fitFont(textEl.textContent.length);
      body.appendChild(textEl);
      c.appendChild(body);
    }
    // link cards show the ACTUAL link preview (image + headline/site) instead of a 🔗
    if (isLink && !hasImage && textEl) enrichLinkCard(p, thumb, textEl, body);
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
    els.main.innerHTML = "";
    var list = filtered();
    if (els.count) {
      var note = S.semanticLoading ? tr("related_searching") : (S.semanticIds && S.q ? tr("semantic") : "");
      els.count.textContent = countN(list.length) + note;
    }
    if (!list.length) {
      els.main.appendChild(el("div", "fb-empty", S.semanticLoading ? tr("searching") : tr("no_results")));
      return;
    }
    var grid = el("div", "fb-grid" + (S.selMode ? " selmode" : "")); els.grid = grid;
    list.slice(0, S.shown).forEach(function (p) { grid.appendChild(card(p)); });
    els.main.appendChild(grid);
    if (S.shown < list.length) {
      var sentinel = el("div", "fb-sentinel");
      els.main.appendChild(sentinel);
      var io = new IntersectionObserver(function (en) { if (en[0].isIntersecting) { io.disconnect(); S.shown += PAGE; renderBrowse(); } });
      io.observe(sentinel);
    }
    updateSelBar();
  }

  /* ── calendar (respects the active search/filter — a temporal view of it) ─ */
  function renderCalendar() {
    // Year is navigated by the calendar's own sidebar, so don't apply the year
    // filter here (the browse year dropdown is hidden on calendar). Type + search
    // still apply, so the chips filter the calendar too.
    var posts = baseList().filter(passType);
    if (els.count) els.count.textContent = countN(posts.length);
    var byDate = {}; posts.forEach(function (p) { (byDate[p.date.slice(0, 10)] = byDate[p.date.slice(0, 10)] || []).push(p); });
    var yrs = Object.keys(posts.reduce(function (a, p) { a[p.date.slice(0, 4)] = 1; return a; }, {})).sort().reverse();
    // if the current month has no matches, jump to the most recent one that does
    if (S.q && yrs.length && yrs.indexOf(String(S.cal.y)) < 0) {
      var latest = posts.map(function (p) { return p.date; }).sort().reverse()[0];
      if (latest) S.cal = { y: +latest.slice(0, 4), m: +latest.slice(5, 7) };
    }
    els.main.innerHTML = "";
    if (S.q) {
      els.main.appendChild(el("div", "fb-cal-search", (EN() ? "\u201c" + S.q + "\u201d search" : "\u2018" + S.q + "\u2019 \uac80\uc0c9") +
        (S.semanticLoading ? tr("related_searching") : (S.semanticIds ? tr("semantic") : "")) +
        "  —  " + countN(posts.length)));
    }
    var wrap = el("div", "fb-cal");
    var side = el("div", "fb-cal-side");
    yrs.forEach(function (y) {
      var n = posts.filter(function (p) { return p.date.indexOf(y) === 0; }).length;
      var b = el("button", "fb-cal-y" + (S.cal.y == y ? " on" : ""), y + " (" + n + ")");
      b.onclick = function () { var ds = posts.filter(function (p) { return p.date.indexOf(y) === 0; }).map(function (p) { return p.date; }).sort().reverse()[0]; S.cal = { y: +y, m: ds ? +ds.slice(5, 7) : 12 }; renderCalendar(); };
      side.appendChild(b);
    });
    if (!yrs.length) side.appendChild(el("div", "fb-cal-empty", tr("no_results2")));
    wrap.appendChild(side);

    var main = el("div", "fb-cal-main");
    // A sparse year (few posts — incl. any search) shows a compact by-date agenda
    // instead of a 12-month grid you'd have to click through. Dense years → grid.
    var yearPosts = posts.filter(function (p) { return p.date.indexOf(String(S.cal.y)) === 0; })
      .sort(function (a, b) { return a.date < b.date ? 1 : -1; });
    if (yearPosts.length && yearPosts.length <= 50) {
      main.appendChild(el("div", "fb-cal-head2", yearN(S.cal.y) + "  ·  " + countN(yearPosts.length)));
      var ag = el("div", "fb-agenda"), lastDay = "";
      yearPosts.forEach(function (p) {
        var day = p.date.slice(0, 10);
        if (day !== lastDay) { ag.appendChild(el("div", "fb-agenda-date", day)); lastDay = day; }
        var row = el("div", "fb-agenda-row");
        row.appendChild(el("span", "fb-badge " + p.type, typeLabel(p.type)));
        row.appendChild(el("span", "fb-agenda-t", p.title || tr("untitled")));
        row.onclick = function () { openPost(p.id, yearPosts.map(function (x) { return x.id; })); };
        ag.appendChild(row);
      });
      main.appendChild(ag);
    } else {
      var head = el("div", "fb-cal-head");
      var prev = el("button", "fb-nav", "‹"); prev.onclick = function () { step(-1); };
      var next = el("button", "fb-nav", "›"); next.onclick = function () { step(1); };
      head.appendChild(prev); head.appendChild(el("div", "fb-cal-title", ymTitle(S.cal.y, S.cal.m))); head.appendChild(next);
      main.appendChild(head);
      var g = el("div", "fb-cal-grid");
      tr("mon").split("").forEach(function (d) { g.appendChild(el("div", "fb-dow", d)); });
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
          var a = el("div", "fb-ev " + p.type, p.title || tr("untitled")); a.title = p.excerpt || p.title || "";
          a.onclick = function () { openPost(p.id, dayItems.map(function (x) { return x.id; })); };
          cell.appendChild(a);
        });
        if (dayItems.length > 4) {
          var more = el("div", "fb-more", moreN(dayItems.length - 4));
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
    var x = el("button", "fb-x", "×"); x.title = tr("close"); x.onclick = closeDayPanel;
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
    els.dayPopTitle.textContent = ds + "  ·  " + countN(items.length);
    els.dayPopList.innerHTML = "";
    items.forEach(function (p) {
      var row = el("div", "fb-agenda-row");
      row.appendChild(el("span", "fb-badge " + p.type, typeLabel(p.type)));
      var t = el("span", "fb-agenda-t", p.title || tr("untitled"));
      row.appendChild(t);
      if (p.thumb) { var im = el("img", "fb-daypop-thumb"); im.loading = "lazy"; im.src = p.thumb; im.onerror = function () { im.remove(); }; row.appendChild(im); }
      row.onclick = function () { closeDayPanel(); openPost(p.id, items.map(function (x) { return x.id; })); };
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
    document.addEventListener("keydown", function (e) {
      if (!els.modal.classList.contains("on") || S.lb) return;   // lightbox (if open) owns the keys
      if (e.key === "Escape") closePost();
      else if (e.key === "ArrowLeft") docNav(-1);
      else if (e.key === "ArrowRight") docNav(1);
    });
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
    if (p && p.url) { var o = el("a", "fb-orig", tr("view_original")); o.href = p.url; o.target = "_blank"; o.rel = "noopener"; bar.appendChild(o); }
    // context prev/next — walk every item in the list the user came from
    var ctxPos = (S.ctx && S.ctx.length > 1) ? S.ctx.indexOf(id) : -1;
    if (ctxPos >= 0) {
      var nav = el("div", "fb-doc-nav");
      var pv = el("button", "fb-doc-navbtn", "‹"); pv.title = tr("prev"); pv.onclick = function () { docNav(-1); };
      var nx = el("button", "fb-doc-navbtn", "›"); nx.title = tr("next"); nx.onclick = function () { docNav(1); };
      var posEl = el("div", "fb-doc-pos", (ctxPos + 1) + " / " + S.ctx.length);
      // scrubber — drag to skip hundreds/thousands; release to jump there.
      var sld = el("input"); sld.type = "range"; sld.className = "fb-doc-slider";
      sld.min = 0; sld.max = S.ctx.length - 1; sld.value = ctxPos; sld.title = tr("lb_goto");
      sld.addEventListener("input", function () { posEl.textContent = (+sld.value + 1) + " / " + S.ctx.length; });
      sld.addEventListener("change", function () { openPost(S.ctx[+sld.value], S.ctx); });
      nav.appendChild(pv); nav.appendChild(sld); nav.appendChild(nx); nav.appendChild(posEl);
      bar.appendChild(nav);
    }
    // privacy toggle — private gates sharing/export only (still shown locally)
    if (p && p.fbid) {
      var pvb = el("button", "fb-doc-priv");
      var setLbl = function () { pvb.textContent = p.private ? "🔒 " + tr("private") : "🌐 " + tr("public"); pvb.className = "fb-doc-priv" + (p.private ? " on" : ""); };
      setLbl(); pvb.title = tr("privacy_hint");
      pvb.onclick = function () {
        var next = p.private ? "public" : "private";
        fetch("/api/privacy", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ fbid: p.fbid, privacy: next }) })
          .then(function (r) { return r.json(); })
          .then(function (res) { p.private = !!res.private; setLbl(); })
          .catch(function () {});
      };
      bar.appendChild(pvb);
      // erase ("hide") toggle — a soft delete; reveal hidden items with 👁 숨김 보기
      var eb = el("button", "fb-doc-priv");
      var setE = function () { eb.textContent = p.erased ? ("♻ " + tr("sel_restore")) : ("🗑 " + tr("sel_erase")); eb.className = "fb-doc-priv" + (p.erased ? " erased" : ""); };
      setE(); eb.title = tr("show_hidden_hint");
      eb.onclick = function () {
        var next = !p.erased;
        fetch("/api/erase", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ fbid: p.fbid, erased: next }) })
          .then(function (r) { return r.json(); })
          .then(function () { p.erased = next; setE(); })
          .catch(function () {});
      };
      bar.appendChild(eb);
    }
    doc.appendChild(bar);
    var body = el("div", "fb-doc-body");
    body.innerHTML = '<div class="fb-loading">' + tr("loading") + '</div>';
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
        // This post's own media, in body order (images then videos) — the instant
        // fallback before the category-wide list (warmed by openPost) arrives.
        var imgs = content.querySelectorAll("img.fb-md-img");
        var media = []; imgs.forEach(function (im) { media.push({ url: im.getAttribute("src"), type: "image", post_id: id, post_title: obj.title || "" }); });
        var imgN = media.length;
        vids.forEach(function (u) { media.push({ url: u, type: "video", post_id: id, post_title: obj.title || "" }); });
        imgs.forEach(function (im, ix) { im.style.cursor = "zoom-in"; im.onclick = function () { openMediaLightbox(media, ix, im.getAttribute("src")); }; });
        // Keep inline video players (first autoplays), plus a ⛶ button that opens the
        // category lightbox at that video — so 영상 navigates the whole category too.
        vids.forEach(function (u, vi) {
          var wrap = el("div", "fb-doc-vidwrap");
          var v = el("video", "fb-doc-vid"); v.src = u; v.controls = true; v.preload = "metadata"; v.playsInline = true; if (vi === 0) v.autoplay = true;
          wrap.appendChild(v);
          var exp = el("button", "fb-doc-videxpand", "⛶"); exp.title = tr("lb_expand");
          exp.onclick = (function (idx, url) { return function () { openMediaLightbox(media, idx, url); }; })(imgN + vi, u);
          wrap.appendChild(exp);
          content.appendChild(wrap);
          if (vi === 0) v.play().catch(function () { });
        });
        appendLinkPreviews(content);
        appendRelated(doc, id);
      })
      .catch(function () {
        body.innerHTML = "";
        body.appendChild(el("h1", null, p ? p.title : ""));
        if (p && p.excerpt) body.appendChild(el("p", null, p.excerpt));
        var note = el("p", "fb-off", tr("load_body_fail"));
        if (p && p.url) { var a = el("a", "fb-orig", tr("view_original")); a.href = p.url; a.target = "_blank"; note.appendChild(document.createTextNode(" ")); note.appendChild(a); }
        body.appendChild(note);
        appendRelated(doc, id);
      });
  }

  function appendRelated(doc, id) {
    var ids = (S.related[id] || []).map(function (rid) { return S.byId[rid]; }).filter(Boolean).slice(0, 8);
    if (!ids.length) return;
    var rel = el("div", "fb-rel"); rel.appendChild(el("h3", null, tr("related")));
    var grid = el("div", "fb-rel-grid");
    ids.forEach(function (rp) {
      var c = el("div", "fb-rel-card"); c.onclick = function () { openPost(rp.id); };
      if (rp.thumb) { var im = el("img", "ri"); im.loading = "lazy"; im.src = rp.thumb; im.onerror = function () { im.remove(); }; c.appendChild(im); }
      c.appendChild(el("div", "rt", rp.title || tr("untitled")));
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
      card.appendChild(el("div", "fb-prev-body", tr("link_preview")));
      wrap.appendChild(card);
      unfurl(u).then(function (d) {
        card.classList.remove("loading"); card.innerHTML = "";
        if (d && d.ok && d.image) { var im = el("img", "fb-prev-img"); im.loading = "lazy"; im.src = d.image; im.onerror = function () { im.remove(); }; card.appendChild(im); }
        var b = el("div", "fb-prev-body");
        var site = (d && d.ok && d.site) ? decodeEnt(d.site) : (function () { try { return new URL(u).hostname.replace(/^www\./, ""); } catch (e) { return tr("source_fallback"); } })();
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
  function openPost(id, ctxIds) {
    id = String(id);
    S.ctx = (ctxIds && ctxIds.length) ? ctxIds.map(String) : null;   // null → no prev/next
    ensureCtxMedia(S.ctx);                                           // warm the category media for the lightbox
    if (location.hash.indexOf("#post/") === 0) { history.replaceState(null, "", "#post/" + encodeURIComponent(id)); openDetail(id); }
    else location.hash = "#post/" + encodeURIComponent(id);
  }

  function mediaIndex(media, url) { for (var i = 0; i < media.length; i++) if (media[i].url === url) return i; return -1; }

  /* ── category-wide media for the lightbox ────────────────────────────────────
     Full-screen navigation should walk EVERY photo/video in the current category
     (사진/영상/글/링크/공유/미분류 …), not just the few on one post. Fetch the flat media
     list for the posts on screen (the active context) once, cache it, then open the
     lightbox positioned at the clicked item. */
  function ctxMediaKey(ids) { return ids.length + "|" + (ids[0] || "") + "|" + (ids[ids.length - 1] || ""); }
  function ensureCtxMedia(ids) {
    if (!ids || !ids.length) { S.ctxMedia = null; return null; }
    var key = ctxMediaKey(ids);
    if (S.ctxMedia && S.ctxMedia.key === key) return S.ctxMedia.p;       // cached for this context
    var p = fetch("/api/media", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ids: ids }) })
      .then(function (r) { return r.json(); })
      .then(function (list) {
        var byUrl = {}; for (var i = 0; i < list.length; i++) if (byUrl[list[i].url] == null) byUrl[list[i].url] = i;
        return { list: list, byUrl: byUrl };
      }).catch(function () { return null; });
    S.ctxMedia = { key: key, p: p };
    return p;
  }
  // Show the post's OWN media instantly, then upgrade to the whole category (kept on
  // the same item) once loaded — so opening is never blocked on the category fetch.
  function openMediaLightbox(localItems, idx, url) {
    openLightbox(localItems, idx);
    var p = S.ctxMedia && S.ctxMedia.p;
    if (!p) return;
    p.then(function (full) {
      if (!full || !full.list.length || !S.lb) return;
      var gi = full.byUrl[url];
      if (gi == null) return;                                            // clicked item not in context → keep local
      if (S.lb.items[S.lb.i] && S.lb.items[S.lb.i].url === url) {        // still on the clicked item → expand
        S.lb.items = full.list; S.lb.i = gi; lbRender(); renderLbThumbs();
      }
    });
  }

  /* ── lightbox: full-screen media viewer with prev/next, thumb strip, swipe ── */
  function buildLightbox() {
    els.lb = el("div", "fb-lb");
    var top = el("div", "fb-lb-top");
    var x = el("button", "fb-lb-x", "×"); x.title = tr("close"); x.onclick = closeLightbox;
    els.lbLink = el("a", "fb-lb-link"); els.lbLink.target = "_blank"; els.lbLink.rel = "noopener";
    top.appendChild(x); top.appendChild(els.lbLink);
    els.lbStage = el("div", "fb-lb-stage");
    var prev = el("button", "fb-lb-nav prev", "‹"); prev.onclick = function (e) { e.stopPropagation(); lbGo(-1); };
    var next = el("button", "fb-lb-nav next", "›"); next.onclick = function (e) { e.stopPropagation(); lbGo(1); };
    els.lbCounter = el("div", "fb-lb-count");
    // position scrubber — jump to any image even across thousands of items
    els.lbRange = el("input"); els.lbRange.type = "range"; els.lbRange.min = 0; els.lbRange.className = "fb-lb-range"; els.lbRange.title = tr("lb_goto");
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
    if (href) { els.lbLink.href = href; els.lbLink.textContent = (it.post_title ? it.post_title.slice(0, 46) + "  " : "") + tr("original_short"); els.lbLink.style.display = ""; }
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
  // The list of post ids in the current filtered context (display order), used to
  // power prev/next inside the detail view so it walks the whole context.
  function contextIds() { return filtered().map(function (p) { return p.id; }); }
  // Step to the prev/next post in the active context (S.ctx), wrapping around.
  function docNav(d) {
    if (!S.ctx || S.ctx.length < 2) return;
    var cur = location.hash.indexOf("#post/") === 0 ? decodeURIComponent(location.hash.slice(6)) : null;
    var i = cur ? S.ctx.indexOf(cur) : -1;
    if (i < 0) return;
    openPost(S.ctx[(i + d + S.ctx.length) % S.ctx.length], S.ctx);
  }
  /* ── AI chat (multi-turn, archive-grounded RAG; Gemini) ───────────────── */
  var CHAT_KEY = "ffs.chat.v1";
  function loadChat() { try { S.chat = JSON.parse(sessionStorage.getItem(CHAT_KEY) || "[]") || []; } catch (e) { S.chat = []; } }
  function saveChat() { try { sessionStorage.setItem(CHAT_KEY, JSON.stringify(S.chat.slice(-20))); } catch (e) { /* quota */ } }

  function renderChat() {
    els.main.innerHTML = "";
    var wrap = el("div", "fb-chat");
    var log = el("div", "fb-chat-log"); els.chatLog = log;
    if (!S.chat.length) {
      var hi = el("div", "fb-chat-hi");
      hi.appendChild(el("div", "h", tr("chat_hi")));
      hi.appendChild(el("div", "p", tr("chat_sub")));
      var ex = el("div", "fb-chat-ex");
      [tr("chat_eg1"), tr("chat_eg2"), tr("chat_eg3")].forEach(function (q) {
        var b = el("button", "fb-chat-egg", q); b.onclick = function () { els.chatInput.value = q; sendChat(); };
        ex.appendChild(b);
      });
      hi.appendChild(ex); log.appendChild(hi);
    } else {
      S.chat.forEach(function (m) { log.appendChild(chatBubble(m)); });
    }
    // persist + pill on scroll; "↓ latest" pill appears when scrolled up
    var _logDeb;
    log.addEventListener("scroll", function () { updateChatPill(); clearTimeout(_logDeb); _logDeb = setTimeout(saveScroll, 200); }, { passive: true });
    wrap.appendChild(log);
    els.chatPill = el("button", "fb-chat-pill", "↓"); els.chatPill.title = tr("jump_latest");
    els.chatPill.onclick = function () { scrollChat(); updateChatPill(); };
    wrap.appendChild(els.chatPill);

    var comp = el("div", "fb-chat-composer");
    els.chatInput = el("textarea"); els.chatInput.placeholder = tr("chat_ph"); els.chatInput.rows = 1;
    els.chatInput.addEventListener("input", function () { this.style.height = "auto"; this.style.height = Math.min(this.scrollHeight, 160) + "px"; });
    els.chatInput.addEventListener("keydown", function (e) { if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); sendChat(); } });
    els.chatSend = el("button", "fb-chat-send"); els.chatSend.innerHTML = "↑"; els.chatSend.title = tr("send"); els.chatSend.onclick = sendChat;
    comp.appendChild(els.chatInput); comp.appendChild(els.chatSend);
    // model selector (Gemini flash ⇄ pro), persisted; sent with each chat turn.
    var models = CFG.models && CFG.models.length ? CFG.models : ["gemini-flash-latest"];
    if (models.length > 1) {
      var msel = el("select", "fb-chat-model"); msel.title = tr("ai_model");
      // label by lane (0 = fast, 1 = precise) — the model ids are provider-specific
      models.forEach(function (m, i) { msel.appendChild(new Option(i === 0 ? tr("model_fast") : tr("model_precise"), m)); });
      if (models.indexOf(S.model) < 0) S.model = models[0];   // stale id from another provider → reset
      msel.value = S.model; if (msel.value !== S.model) { S.model = msel.value; }
      msel.onchange = function () { S.model = msel.value; try { localStorage.setItem("ffs.model", S.model); } catch (e) {} };
      comp.appendChild(msel);
    }
    // agent (tool-use) toggle: when on, the AI searches + opens posts via tools
    // for grounded, per-item handling; off = the fast one-shot RAG path.
    var agt = el("button", "fb-chat-agent" + (S.agent ? " on" : ""), tr("tools"));
    agt.title = tr("tools_title");
    agt.onclick = function () { S.agent = !S.agent; try { localStorage.setItem("ffs.agent", S.agent ? "1" : "0"); } catch (e) {} agt.classList.toggle("on", S.agent); };
    comp.appendChild(agt);
    if (S.chat.length) { var clr = el("button", "fb-chat-clear", tr("clear_chat")); clr.onclick = function () { S.chat = []; saveChat(); renderChat(); }; comp.appendChild(clr); }
    wrap.appendChild(comp);
    els.main.appendChild(wrap);
    requestAnimationFrame(restoreChatScroll);   // land back where you left the chat
    setTimeout(function () { if (els.chatInput) els.chatInput.focus(); }, 30);
  }

  /* ── settings page: connect any AI you have (chat provider + embeddings) ──── */
  function _setField(label, value, type) {
    var w = el("div", "fb-set-field");
    w.appendChild(el("label", "fb-set-label", label));
    var i = el("input"); i.type = type || "text"; i.value = value || ""; i.className = "fb-set-input";
    w.appendChild(i); w.input = i; return w;
  }
  function renderSettings() {
    els.main.innerHTML = "";
    var wrap = el("div", "fb-settings");
    wrap.appendChild(el("h2", "fb-set-h", tr("settings")));
    var status = el("div", "fb-set-status");
    function setStatus(msg, cls) { status.textContent = msg || ""; status.className = "fb-set-status" + (cls ? " " + cls : ""); }

    fetch("/api/settings").then(function (r) { return r.json(); }).then(function (d) {
      var CP = d.chat_providers || {};
      // ── Chat AI ──────────────────────────────────────────────────────────
      var cs = el("div", "fb-set-sec");
      cs.appendChild(el("div", "fb-set-sech", tr("set_chat")));
      cs.appendChild(el("div", "fb-set-sub", tr("set_chat_hint")));
      var prov = el("select", "fb-set-input");
      Object.keys(CP).forEach(function (pid) { prov.appendChild(new Option(CP[pid].label + (CP[pid].configured ? "  ✓" : ""), pid)); });
      prov.value = d.chat.provider;
      var provW = el("div", "fb-set-field"); provW.appendChild(el("label", "fb-set-label", tr("set_provider"))); provW.appendChild(prov);
      var fast = _setField(tr("set_fast"), d.chat.fast_model);
      var prec = _setField(tr("set_precise"), d.chat.precise_model);
      var key = _setField(tr("set_key"), "", "password");
      var keyHint = el("div", "fb-set-keyhint");
      var testBtn = el("button", "fb-set-btn", tr("set_test"));
      function syncProv() {
        var p = CP[prov.value] || {};
        fast.input.value = p.fast || ""; prec.input.value = p.precise || "";
        key.input.value = ""; key.input.placeholder = p.configured ? tr("set_key_set") : tr("set_key_ph");
        key.style.display = p.key_env ? "" : "none";
        keyHint.innerHTML = p.signup ? (tr("set_get_key") + ' <a href="' + p.signup + '" target="_blank" rel="noopener">' + p.key_env + ' ↗</a>') : tr("set_no_key");
      }
      prov.onchange = syncProv; syncProv();
      testBtn.onclick = function () {
        setStatus(tr("set_testing"));
        fetch("/api/settings/test", { method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ provider: prov.value, model: fast.input.value, key: key.input.value || undefined }) })
          .then(function (r) { return r.json(); })
          .then(function (res) { setStatus((res.ok ? "✓ " : "✗ ") + res.detail, res.ok ? "ok" : "err"); })
          .catch(function () { setStatus("✗ " + tr("set_err"), "err"); });
      };
      [provW, fast, prec, key, keyHint, testBtn].forEach(function (x) { cs.appendChild(x); });
      wrap.appendChild(cs);

      // ── Semantic search (embeddings) ─────────────────────────────────────
      var es = el("div", "fb-set-sec");
      es.appendChild(el("div", "fb-set-sech", tr("set_embed")));
      es.appendChild(el("div", "fb-set-sub", tr("set_embed_hint")));
      var emb = el("select", "fb-set-input");
      Object.keys(d.embed_providers || {}).forEach(function (pid) { emb.appendChild(new Option(d.embed_providers[pid].label, pid)); });
      emb.value = d.embedding.provider;
      var embW = el("div", "fb-set-field"); embW.appendChild(el("label", "fb-set-label", tr("set_provider"))); embW.appendChild(emb);
      var embModel = _setField(tr("set_model"), d.embedding.model);
      emb.onchange = function () { var p = (d.embed_providers || {})[emb.value] || {}; embModel.input.value = p.model || ""; };
      es.appendChild(embW); es.appendChild(embModel);
      es.appendChild(el("div", "fb-set-note", tr("set_embed_note")));
      wrap.appendChild(es);

      // ── Save ─────────────────────────────────────────────────────────────
      var save = el("button", "fb-set-save", tr("set_save"));
      save.onclick = function () {
        var p = CP[prov.value] || {}; var keys = {};
        if (p.key_env && key.input.value) keys[p.key_env] = key.input.value;
        setStatus(tr("set_saving"));
        fetch("/api/settings", { method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ chat: { provider: prov.value, fast_model: fast.input.value, precise_model: prec.input.value },
            embedding: { provider: emb.value, model: embModel.input.value }, keys: keys }) })
          .then(function (r) { return r.json(); })
          .then(function () { setStatus(tr("set_saved"), "ok"); setTimeout(function () { location.reload(); }, 700); })
          .catch(function () { setStatus("✗ " + tr("set_err"), "err"); });
      };
      var bar = el("div", "fb-set-bar"); bar.appendChild(save); bar.appendChild(status);
      wrap.appendChild(bar);
    }).catch(function () { wrap.appendChild(el("div", "fb-empty", tr("set_err"))); });

    els.main.appendChild(wrap);
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
        im.addEventListener("load", chatImgLoaded);
        var src = im.getAttribute("src"); inlineSet[src] = 1;
        var idx = mediaIndex(media, src);
        if (idx >= 0) { im.style.cursor = "zoom-in"; im.onclick = function () { openLightbox(media, idx); }; }
      });
      var gmedia = media.filter(function (item) { return !inlineSet[item.url]; });
      var gal = el("div", "fb-chat-media");
      var PREV = 11;  // up to 12 tiles; the 12th is "+N" if there are more
      gmedia.slice(0, gmedia.length > 12 ? PREV : 12).forEach(function (item) {
        var cell = el("div", "fb-media-cell" + (item.type === "video" ? " vid" : ""));
        var im = el("img"); im.loading = "lazy"; im.src = item.url; im.alt = item.post_title || ""; im.addEventListener("load", chatImgLoaded);
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
      src.appendChild(el("span", "fb-chat-src-h", tr("sources")));
      m.sources.forEach(function (s) { var p = S.byId[String(s.id)]; if (p) { var a = el("a", null, p.title || p.id); a.href = "#post/" + p.id; src.appendChild(a); } });
      b.appendChild(src);
    }
    if (m.role === "bot" && !m._pending) {
      var foot = el("div", "fb-chat-foot");
      var meta = [];
      if (m.model) meta.push(m.model);
      if (m.steps) meta.push("🔧 " + m.steps + (EN() ? " steps" : "\ub2e8\uacc4"));
      if (m.ms) meta.push((m.ms / 1000).toFixed(1) + (EN() ? "s" : "\ucd08"));
      foot.appendChild(el("div", "fb-chat-meta", meta.join("  ·  ")));
      var act = el("div", "fb-chat-act");
      var copy = el("button", "fb-chat-actbtn", tr("copy")); copy.title = tr("copy_title");
      copy.onclick = function () { copyText(m.content); copy.textContent = tr("copied"); setTimeout(function () { copy.textContent = tr("copy"); }, 1200); };
      var regen = el("button", "fb-chat-actbtn", tr("regen")); regen.title = tr("regen_title"); regen.onclick = function () { regenMessage(m); };
      var del = el("button", "fb-chat-actbtn del", tr("del")); del.title = tr("del_title"); del.onclick = function () { deleteMessage(m); };
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
  // chat images load late (after the bubble renders) and grow the log; re-snap to
  // the bottom when one loads IF the user is already near the bottom (don't yank
  // them back if they've scrolled up to read).
  function chatImgLoaded() { if (els.chatLog && (els.chatLog.scrollHeight - els.chatLog.scrollTop - els.chatLog.clientHeight) < 160) scrollChat(); }
  // Rebuild the log. mode: "anchor" → ride the newest question to the top (so the
  // answer renders below it); "bottom" → jump to bottom; default → keep position
  // unless the user was already at the bottom (then follow). Predictable, no yank.
  function redrawChat(mode) {
    if (!els.chatLog) { renderChat(); return; }
    var prev = els.chatLog.scrollTop, wasBottom = isChatBottom();
    els.chatLog.innerHTML = "";
    S.chat.forEach(function (m) { els.chatLog.appendChild(chatBubble(m)); });
    if (mode === "anchor") anchorLastUser();
    else if (mode === "bottom" || wasBottom) scrollChat();
    else els.chatLog.scrollTop = prev;
    updateChatPill();
  }

  function sendChat() {
    if (S.chatBusy || !els.chatInput) return;
    var text = (els.chatInput.value || "").trim();
    if (!text) return;
    els.chatInput.value = ""; els.chatInput.style.height = "auto";
    S.chat.push({ role: "user", content: text });
    S.chat.push({ role: "bot", content: "", _pending: true });
    redrawChat("anchor"); sendRequest();
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
      .then(function (res) { pending._pending = false; pending.content = res.answer || tr("no_response"); pending.sources = res.sources || []; pending.media = res.media || []; pending.model = res.model || ""; pending.steps = res.steps || 0; pending.ms = Date.now() - t0; })
      .catch(function (err) { pending._pending = false; pending.content = (err === 429) ? tr("err_busy") : tr("err_unavailable"); })
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
