!(function () {
  "use strict";
  var r = window.location,
    a = window.document,
    t = window.localStorage,
    o = a.currentScript,
    l = o.getAttribute("data-api") || new URL(o.src).origin + "/api/event",
    w = t && t.plausible_ignore;
  function s(t) {
    console.warn("Ignoring Event: " + t);
  }
  function e(t, e) {
    if (
      /^localhost$|^127(\.[0-9]+){0,2}\.[0-9]+$|^\[::1?\]$/.test(r.hostname) ||
      "file:" === r.protocol
    )
      return s("localhost");
    if (
      !(
        window._phantom ||
        window.__nightmare ||
        window.navigator.webdriver ||
        window.Cypress
      )
    ) {
      if ("true" == w) return s("localStorage flag");
      var n = {};
      (n.n = t),
        (n.u = e.u || r.href),
        (n.d = e.d || o.getAttribute("data-domain")),
        (n.r = a.referrer || null),
        (n.w = window.innerWidth),
        e && e.meta && (n.m = JSON.stringify(e.meta)),
        e && e.props && (n.p = JSON.stringify(e.props));
      var i = new XMLHttpRequest();
      i.open("POST", l, !0),
        i.setRequestHeader("Content-Type", "text/plain"),
        i.send(JSON.stringify(n)),
        (i.onreadystatechange = function () {
          4 == i.readyState && e && e.callback && e.callback();
        });
    }
  }
  var n = (window.plausible && window.plausible.q) || [];
  window.plausible = e;
  for (var i = 0; i < n.length; i++) e.apply(this, n[i]);
})();
window.plausible =
  window.plausible ||
  function () {
    (window.plausible.q = window.plausible.q || []).push(arguments);
  };
var clubSlug = window.document.currentScript.dataset.clubSlug;
var analyticsUrl = clubSlug
  ? "https://www.routechoices.com/" + clubSlug + window.location.pathname
  : window.location.href;
window.plausible("pageview", { u: analyticsUrl }); // global stats
if (clubSlug) {
  window.plausible("pageview", { d: clubSlug + ".routechoices.com" }); // site stats
}
