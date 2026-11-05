// Small helpers shared by the Dashboard, Trips and Days Replay pages.
window.Finds = (function () {
  "use strict";
  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

  function esc(s) {
    return String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  function parts(iso) { return iso.split("-").map(Number); }

  // "Tue 20 Oct 2026"
  function prettyDate(iso) {
    const [y, m, d] = parts(iso);
    return WEEKDAYS[new Date(Date.UTC(y, m - 1, d)).getUTCDay()] + " " + d + " " + MONTHS[m - 1] + " " + y;
  }

  // "Sat 1 Jul – Sun 9 Jul 2023", or one date when start and end are the same
  function dateRange(start, end) {
    if (start === end) return prettyDate(start);
    const a = prettyDate(start), b = prettyDate(end);
    return (start.slice(0, 4) === end.slice(0, 4) ? a.slice(0, -5) : a) + " – " + b;
  }

  // Calendar days from start to end, counting both
  function daySpan(start, end) {
    const [y1, m1, d1] = parts(start), [y2, m2, d2] = parts(end);
    return Math.round((Date.UTC(y2, m2 - 1, d2) - Date.UTC(y1, m1 - 1, d1)) / 86400000) + 1;
  }

  // Province / state (or country outside Canada and the US) for a stop
  function region(stop) {
    if (stop.state && stop.state !== "None") return stop.state;
    return stop.country || "";
  }

  // "Utah, Idaho & Nevada" from the stops, most-visited first
  function regionsText(stops, max = 3) {
    const counts = new Map();
    for (const s of stops) {
      const r = region(s);
      if (r) counts.set(r, (counts.get(r) || 0) + 1);
    }
    const names = [...counts.keys()].sort((a, b) => counts.get(b) - counts.get(a));
    const shown = names.slice(0, max);
    const more = names.length - shown.length;
    if (more > 0) return shown.join(", ") + " & " + more + " more";
    return shown.length > 1 ? shown.slice(0, -1).join(", ") + " & " + shown[shown.length - 1] : (shown[0] || "");
  }

  // The caching days (newest first) inside a trip's date range
  function tripDays(trip, days) {
    return days.filter(d => d.date >= trip.start && d.date <= trip.end);
  }

  // Place levels for Browse by Location: country > province/state > town.
  // "near Wabamun" counts as Wabamun.
  const PLACE_LEVELS = ["country", "state", "town"];
  function placeValue(stop, level) {
    if (level === "country") return stop.country || "Unknown country";
    if (level === "state") return stop.state && stop.state !== "None" ? stop.state : "Other";
    return stop.town || "Unnamed area";
  }
  function inPlace(stop, place) {
    return PLACE_LEVELS.every(l => !place[l] || placeValue(stop, l) === place[l]);
  }

  function plural(n, word) { return n.toLocaleString("en-CA") + " " + word + (n === 1 ? "" : "s"); }

  // If the pages are shown by a plain web server (such as `python3 -m http.server`)
  // instead of serve.py, trips, favourites, places and settings can't load and the
  // pages look empty. Say so plainly at the top of every page, so it isn't
  // mistaken for lost data.
  function checkServer() {
    if (!location.protocol.startsWith("http")) return;   // opened as a file: pages say so themselves
    fetch("api/settings", { cache: "no-store" })
      .then(r => r.ok && (r.headers.get("Content-Type") || "").includes("json"))
      .catch(() => false)
      .then(ok => {
        if (ok || document.getElementById("server-warning")) return;
        const bar = document.createElement("div");
        bar.id = "server-warning";
        bar.setAttribute("role", "alert");
        bar.style.cssText = "position:sticky;top:0;z-index:10000;background:#fde68a;color:#3b2f00;" +
          "border-bottom:2px solid #d97706;padding:10px 16px;font:14px/1.4 -apple-system,system-ui,sans-serif;";
        bar.innerHTML = "<strong>Your trips, favourites and places aren't showing because this isn't serve.py.</strong> " +
          "They're safe in this folder. In Terminal, stop the current server with Control-C, then run " +
          "<code style=\"background:rgba(0,0,0,.08);padding:1px 5px;border-radius:4px\">python3 serve.py</code> " +
          "and refresh this page.";
        document.body.prepend(bar);
      });
  }
  if (document.body) checkServer(); else document.addEventListener("DOMContentLoaded", checkServer);

  return { MONTHS, WEEKDAYS, esc, prettyDate, dateRange, daySpan, region, regionsText, tripDays, plural,
    PLACE_LEVELS, placeValue, inPlace };
})();
