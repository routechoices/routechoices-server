(function () {
  var d = document.currentScript.dataset;
  window.local = {};
  for (var f in d) {
    window.local[f] = d[f];
  }
})();
