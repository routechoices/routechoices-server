(function () {
  u(".date-utc").each(function (el) {
    $el = u(el);
    $el.text(dayjs($el.data("date")).local().format("LLLL"));
  });
  var tooltipTriggerList = [].slice.call(
    document.querySelectorAll('[data-bs-toggle="tooltip"]')
  );
  tooltipTriggerList.map(function (tooltipTriggerEl) {
    return new bootstrap.Tooltip(tooltipTriggerEl);
  });

  if ("IntersectionObserver" in window) {
    document.addEventListener("DOMContentLoaded", function () {
      function handleIntersection(entries) {
        entries.map((entry) => {
          if (entry.isIntersecting && entry.target.dataset.bgImg) {
            // Item has crossed our observation
            // threshold - load src from data-src
            entry.target.style.background =
              "linear-gradient(to right, var(--rc-color-from-trans), var(--rc-color-to-trans)), url('" +
              entry.target.dataset.bgImg +
              "')";
            // Job done for this item - no need to watch it!
            observer.unobserve(entry.target);
          }
        });
      }

      const events = document.querySelectorAll(".event-card");
      const observer = new IntersectionObserver(handleIntersection, {
        rootMargin: "100px",
      });
      events.forEach((event) => observer.observe(event));
    });
  } else {
    // No interaction support? Load all background images automatically
    const events = document.querySelectorAll(".event-card");
    events.forEach((event) => {
      if (event.dataset.bgImg) {
        event.style.background =
          "linear-gradient(to right, var(--rc-color-from-trans), var(--rc-color-to-trans)), url('" +
          header.dataset.bgImg +
          "')";
      }
    });
  }
})();
