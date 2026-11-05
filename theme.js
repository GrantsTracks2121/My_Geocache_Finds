// Light / dark mode for every page. Loaded in each page's <head> so the
// colours are right before anything is drawn. The choice (light, dark, or
// auto = follow the Mac) is saved in settings.json by serve.py; a copy is kept
// in this browser so the page doesn't flash the wrong colours while loading.
(function () {
  "use strict";
  const root = document.documentElement;
  const darkQuery = window.matchMedia ? matchMedia("(prefers-color-scheme: dark)") : null;
  let mode = "light";

  function apply(m) {
    mode = m === "dark" || m === "auto" ? m : "light";
    const dark = mode === "dark" || (mode === "auto" && darkQuery && darkQuery.matches);
    root.dataset.theme = dark ? "dark" : "light";
    root.dataset.themeMode = mode;
  }

  let saved = null;
  try { saved = localStorage.getItem("theme"); } catch (err) { /* storage unavailable */ }
  apply(saved || "light");

  // Called by the Dashboard's Theme setting
  window.setTheme = function (m) {
    try { localStorage.setItem("theme", m); } catch (err) { /* ignore */ }
    apply(m);
  };

  if (darkQuery) darkQuery.addEventListener("change", () => apply(mode));

  if (location.protocol.startsWith("http")) {
    fetch("api/settings", { cache: "no-store" })
      .then(r => (r.ok ? r.json() : null))
      .then(j => { if (j && j.theme && j.theme !== mode) window.setTheme(j.theme); })
      .catch(() => {});
  }
})();
