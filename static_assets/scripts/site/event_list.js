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
})();
