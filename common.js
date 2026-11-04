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

  function plural(n, word) { return n.toLocaleString("en-CA") + " " + word + (n === 1 ? "" : "s"); }

  return { MONTHS, WEEKDAYS, esc, prettyDate, dateRange, daySpan, region, regionsText, tripDays, plural };
})();
