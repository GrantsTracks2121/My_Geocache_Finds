// Search box shared by every page: finds caches (by name or GC code), places
// (towns, neighbourhoods, provinces and countries), trips, and words in your logs.
// It fills <div id="site-search"></div>, wherever the page puts one.
// Needs data/days.js and common.js loaded first.
(function () {
  "use strict";
  const mount = document.getElementById("site-search");
  if (!mount) return;
  const F = window.Finds;
  const DAYS = window.GEOCACHE_DAYS || [];
  const SHOW = 5;          // results per group before "Show all"
  const SHOW_ALL = 200;    // most results a group lists after "Show all"
  const FIND_LOGS = new Set(["Found it", "Attended", "Webcam Photo Taken"]);

  // ---------- look ----------
  const css = document.createElement("style");
  css.textContent = `
  .site-search { position: relative; }
  .site-search.nav-search { margin-left: auto; width: 280px; align-self: center; }
  .site-search.side-search { margin: 0 0 12px; }
  @media (max-width: 700px) { .site-search.nav-search { margin-left: 0; width: 100%; } }
  .site-search input { -webkit-appearance: none; appearance: none; width: 100%; font: inherit; font-size: 13px; padding: 6px 10px 6px 28px;
    border: 1px solid var(--line); border-radius: 6px; background: var(--field, #fff); color: var(--ink); }
  .site-search input:focus { outline: 2px solid var(--accent); outline-offset: -1px; }
  .site-search .glass { position: absolute; left: 9px; top: 50%; transform: translateY(-50%);
    color: var(--muted); pointer-events: none; }
  .site-search .results { position: absolute; top: calc(100% + 4px); width: 460px; max-width: calc(100vw - 24px);
    max-height: min(70vh, 560px); overflow-y: auto; background: var(--panel); color: var(--ink);
    border: 1px solid var(--line); border-radius: 8px; box-shadow: 0 8px 24px rgba(0,0,0,.18);
    z-index: 3000; font-size: 14px; line-height: 1.35; text-align: left; }
  .site-search.right .results { right: 0; }
  .site-search.left .results { left: 0; }
  .site-search .grp { display: flex; justify-content: space-between; padding: 10px 12px 4px;
    font-size: 11px; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: .06em; }
  .site-search a.hit { display: flex; gap: 10px; padding: 7px 12px; color: inherit; text-decoration: none;
    border-top: 1px solid var(--line); }
  .site-search a.hit:hover, .site-search a.hit.on { background: var(--row-hover, #f3f6f4); }
  .site-search .ico { flex: none; width: 18px; text-align: center; color: var(--muted); }
  .site-search .main { min-width: 0; }
  .site-search .sub { font-size: 12px; color: var(--muted); }
  .site-search .code { font: 12px ui-monospace, SFMono-Regular, Menlo, monospace; color: var(--muted); margin-right: 4px; }
  .site-search mark { background: var(--pick, #fbf1d2); color: inherit; border-radius: 2px; }
  .site-search .tag { font-size: 11px; font-weight: 600; padding: 0 5px; border-radius: 4px; margin-left: 6px;
    color: var(--danger); border: 1px solid var(--danger-line, #e4c3b5); background: var(--danger-bg, #fbeee8); }
  .site-search button.more { display: block; width: 100%; text-align: left; font: inherit; font-size: 12px;
    color: var(--accent); background: none; border: 0; border-top: 1px solid var(--line); padding: 6px 12px 6px 40px;
    cursor: pointer; }
  .site-search button.more:hover { text-decoration: underline; }
  .site-search .empty { padding: 12px; color: var(--muted); font-size: 13px; }
  `;
  document.head.appendChild(css);

  mount.classList.add("site-search");
  mount.innerHTML = '<svg class="glass" aria-hidden="true" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
    'stroke-width="2.4" stroke-linecap="round"><circle cx="10.5" cy="10.5" r="6.5"/><path d="M15.5 15.5 21 21"/></svg>' +
    '<input type="search" placeholder="Search caches, places, trips" title="Cache names, GC codes, places, trips and your logs (press / to jump here)" aria-label="Search your finds" ' +
    'autocomplete="off" spellcheck="false" role="combobox" aria-expanded="false" aria-controls="site-search-results">' +
    '<div class="results" id="site-search-results" role="listbox" hidden></div>';
  const input = mount.querySelector("input");
  const box = mount.querySelector(".results");

  // ---------- data, prepared on first use ----------
  // Lower case, accents removed, so "quebec" finds Québec
  const norm = s => String(s ?? "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

  let LOGS = null, PLACES = null, TRIPS = [];
  function prepare() {
    if (LOGS) return;
    LOGS = [];
    const places = new Map();
    const addPlace = (key, name, kind, sub, href) => {
      let p = places.get(key);
      if (!p) places.set(key, p = { name, n: norm(name), kind, sub, href, finds: 0 });
      return p;
    };
    for (const d of DAYS) {
      for (const s of d.stops) {
        const country = F.placeValue(s, "country"), state = F.placeValue(s, "state"), town = F.placeValue(s, "town");
        const counts = FIND_LOGS.has(s.log);
        LOGS.push({ date: d.date, s, key: norm(s.code + " " + s.name), text: null });
        // Each level of Browse by Location, plus neighbourhoods (which open their town)
        const at = (o) => "location.html?" + new URLSearchParams(o).toString();
        const hits = [
          addPlace("c|" + country, country, "country", "Country", at({ country })),
          addPlace("s|" + country + "|" + state, state, "state", country, at({ country, state })),
          addPlace("t|" + country + "|" + state + "|" + town, town, "town", state + ", " + country, at({ country, state, town })),
        ];
        if (s.area) hits.push(addPlace("a|" + country + "|" + state + "|" + town + "|" + s.area, s.area, "area",
          "Neighbourhood in " + town + ", " + state, at({ country, state, town })));
        if (counts) for (const p of hits) p.finds++;
      }
    }
    PLACES = [...places.values()].filter(p => p.name !== "Other" && !p.name.startsWith("Unknown") && p.name !== "Unnamed area");
  }
  function logText(l) { return l.text ??= norm(l.s.text); }

  fetch("api/trips", { cache: "no-store" })
    .then(r => r.ok ? r.json() : { trips: [] })
    .then(j => { TRIPS = (j.trips || []).map(t => ({ ...t, n: norm(t.name), nn: norm(t.note) })); if (!box.hidden) run(); })
    .catch(() => {});

  // ---------- matching ----------
  // Highlights the first match of q in s (matching ignores case and accents)
  function mark(s, q) {
    s = String(s ?? "");
    const i = norm(s).indexOf(q);
    if (i < 0 || !q) return F.esc(s);
    return F.esc(s.slice(0, i)) + "<mark>" + F.esc(s.slice(i, i + q.length)) + "</mark>" + F.esc(s.slice(i + q.length));
  }
  // A short piece of a log around the match
  function snippet(text, q) {
    const flat = String(text).replace(/\[([^\]]*)\]\([^)]*\)/g, "$1").replace(/[*_#>`]/g, "").replace(/\s+/g, " ");
    const i = norm(flat).indexOf(q);
    if (i < 0) return F.esc(flat.slice(0, 90));
    const a = Math.max(0, i - 40), b = Math.min(flat.length, i + q.length + 60);
    return (a ? "…" : "") + mark(flat.slice(a, b), q) + (b < flat.length ? "…" : "");
  }
  const dayHref = l => "day-replay.html?date=" + l.date + "&cache=" + l.s.logId;
  // Starts with the words first, then anywhere
  const rank = (n, q) => n.startsWith(q) ? 0 : n.includes(" " + q) ? 1 : 2;

  let expanded = new Set();
  let lastQ = "";

  function search(q) {
    prepare();
    const places = PLACES.filter(p => p.n.includes(q))
      .sort((a, b) => rank(a.n, q) - rank(b.n, q) || b.finds - a.finds);
    const trips = TRIPS.filter(t => t.n.includes(q) || t.nn.includes(q)).sort((a, b) => b.start.localeCompare(a.start));
    const caches = LOGS.filter(l => l.key.includes(q))
      .sort((a, b) => (norm(b.s.code) === q) - (norm(a.s.code) === q) || rank(norm(a.s.name), q) - rank(norm(b.s.name), q) ||
        b.date.localeCompare(a.date));
    const inCaches = new Set(caches);
    const logs = q.length < 3 ? [] : LOGS.filter(l => !inCaches.has(l) && logText(l).includes(q));
    return { places, trips, caches, logs };
  }

  const KIND_ICON = { country: "🌐", state: "🗺", town: "📍", area: "📍" };
  function hit(href, icon, main, sub) {
    return '<a class="hit" role="option" href="' + F.esc(href) + '"><span class="ico" aria-hidden="true">' + icon +
      '</span><span class="main"><div>' + main + '</div><div class="sub">' + sub + "</div></span></a>";
  }
  function group(id, title, list, draw) {
    if (!list.length) return "";
    const limit = expanded.has(id) ? SHOW_ALL : SHOW;
    let h = '<div class="grp"><span>' + title + "</span><span>" + list.length.toLocaleString("en-CA") + "</span></div>";
    h += list.slice(0, limit).map(draw).join("");
    if (list.length > limit) {
      h += '<button type="button" class="more" data-more="' + id + '">' +
        (limit === SHOW ? "Show " + (list.length > SHOW_ALL ? "the first " + SHOW_ALL : "all " + list.length.toLocaleString("en-CA")) : "Showing the first " + SHOW_ALL) +
        "</button>";
    }
    return h;
  }
  function where(s, q) {
    const town = s.town ? (s.near ? "near " : "") + mark(s.town, q) : "";
    return [town + (s.area ? " (" + mark(s.area, q) + ")" : ""), mark(F.region(s), q)].filter(Boolean).join(", ");
  }

  function run() {
    const raw = input.value.trim();
    const q = norm(raw);
    if (q !== lastQ) { expanded = new Set(); lastQ = q; }
    if (q.length < 2) { close(); return; }
    const r = search(q);
    let h = "";
    h += group("places", "Places", r.places, p =>
      hit(p.href, KIND_ICON[p.kind], mark(p.name, q), F.esc(p.sub) + " · " + F.plural(p.finds, "find")));
    h += group("trips", "Trips", r.trips, t =>
      hit("day-replay.html?trip=" + encodeURIComponent(t.id), "🧭", mark(t.name, q),
        F.esc(F.dateRange(t.start, t.end)) + (t.nn.includes(q) && !t.n.includes(q) ? " · " + snippet(t.note, q) : "")));
    h += group("caches", "Caches", r.caches, l =>
      hit(dayHref(l), "📦", '<span class="code">' + mark(l.s.code, q) + "</span>" + mark(l.s.name, q) +
        (l.s.log === "Didn't find it" ? '<span class="tag">DNF</span>' : ""),
        F.esc(l.s.type) + " · " + where(l.s, q) + " · " + F.esc(F.prettyDate(l.date))));
    h += group("logs", "Mentioned in your logs", r.logs, l =>
      hit(dayHref(l), "💬", F.esc(l.s.name), snippet(l.s.text, q) + " · " + F.esc(F.prettyDate(l.date))));
    if (!h) h = '<div class="empty">Nothing matches “' + F.esc(raw) + "”." +
      (q.length < 3 ? " Logs are searched from 3 letters." : "") + "</div>";
    box.innerHTML = h;
    open();
  }

  // ---------- opening, closing and the keyboard ----------
  function open() { box.hidden = false; input.setAttribute("aria-expanded", "true"); }
  function close() { box.hidden = true; input.setAttribute("aria-expanded", "false"); }
  function place() {   // open the list toward whichever side has room
    const r = mount.getBoundingClientRect();
    mount.classList.toggle("right", r.left > window.innerWidth / 2);
    mount.classList.toggle("left", r.left <= window.innerWidth / 2);
  }

  let timer = 0;
  input.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(run, 120); });
  input.addEventListener("focus", () => { place(); if (input.value.trim().length >= 2) run(); });
  box.addEventListener("mousedown", e => { if (e.target.closest("button.more")) e.preventDefault(); });
  box.addEventListener("click", e => {
    const more = e.target.closest("button.more");
    if (!more) return;
    expanded.add(more.dataset.more);
    const top = box.scrollTop;
    run();
    box.scrollTop = top;
    input.focus();
  });
  document.addEventListener("mousedown", e => { if (!mount.contains(e.target)) close(); });

  input.addEventListener("keydown", e => {
    const hits = [...box.querySelectorAll("a.hit")];
    const at = hits.findIndex(a => a.classList.contains("on"));
    const move = i => {
      hits.forEach(a => a.classList.remove("on"));
      if (hits[i]) { hits[i].classList.add("on"); hits[i].scrollIntoView({ block: "nearest" }); }
    };
    if (e.key === "ArrowDown") { e.preventDefault(); if (box.hidden) run(); else move(Math.min(hits.length - 1, at + 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); move(Math.max(0, at - 1)); }
    else if (e.key === "Enter" && !box.hidden) {
      const a = hits[at >= 0 ? at : 0];
      if (a) { e.preventDefault(); location.href = a.href; }
    } else if (e.key === "Escape") {
      if (!box.hidden) close(); else { input.value = ""; input.blur(); }
    }
  });

  // Press / anywhere (outside a text box) to jump to the search
  document.addEventListener("keydown", e => {
    if (e.key !== "/" || e.metaKey || e.ctrlKey || e.altKey) return;
    const t = e.target;
    if (t.closest && t.closest("input, textarea, select, [contenteditable]")) return;
    e.preventDefault();
    input.focus();
    input.select();
  });
})();
