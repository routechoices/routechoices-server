!(function () {
  "use strict";
  var a = window.location,
    r = window.document,
    o = r.currentScript,
    l = o.getAttribute("data-api") || new URL(o.src).origin + "/api/event";
  function s(t, e) {
    t && console.warn("Ignoring Event: " + t), e && e.callback && e.callback();
  }
  function t(t, e) {
    if (
      /^localhost$|^127(\.[0-9]+){0,2}\.[0-9]+$|^\[::1?\]$/.test(a.hostname) ||
      "file:" === a.protocol
    )
      return s("localhost", e);
    if (
      window._phantom ||
      window.__nightmare ||
      window.navigator.webdriver ||
      window.Cypress
    )
      return s(null, e);
    try {
      if ("true" === window.localStorage.plausible_ignore)
        return s("localStorage flag", e);
    } catch (t) {}
    var n = {},
      i =
        ((n.n = t),
        (n.u = e.u || a.href),
        (n.d = e.d || o.getAttribute("data-domain")),
        (n.r = r.referrer || null),
        e && e.meta && (n.m = JSON.stringify(e.meta)),
        e && e.props && (n.p = e.props),
        new XMLHttpRequest());
    i.open("POST", l, !0),
      i.setRequestHeader("Content-Type", "text/plain"),
      i.send(JSON.stringify(n)),
      (i.onreadystatechange = function () {
        4 === i.readyState && e && e.callback && e.callback();
      });
  }
  var e = (window.plausible && window.plausible.q) || [];
  window.plausible = t;
  for (var n, i = 0; i < e.length; i++) t.apply(this, e[i]);
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
