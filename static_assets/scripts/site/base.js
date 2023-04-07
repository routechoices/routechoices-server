function respondToVisibility(element, callback) {
  var options = {
    root: document.documentElement,
  };

  var observer = new IntersectionObserver((entries, observer) => {
    entries.forEach((entry) => {
      callback(entry.intersectionRatio > 0);
    });
  }, options);

  observer.observe(element);
}

(function () {
  var t = document.getElementById("navbar-toogler");
  if (t) {
    respondToVisibility(t, (visible) => {
      if (visible) {
        document
          .querySelectorAll(".if-collapsed")
          .forEach((el) => (el.style.display = "block"));
        document
          .querySelectorAll(".if-not-collapsed")
          .forEach((el) => (el.style.display = "none"));
      } else {
        document
          .querySelectorAll(".if-collapsed")
          .forEach((el) => (el.style.display = "none"));
        document
          .querySelectorAll(".if-not-collapsed")
          .forEach((el) => (el.style.display = "block"));
      }
    });
  }
})();
