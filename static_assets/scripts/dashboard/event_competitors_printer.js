(function () {
  u("#print-btn").on("click", function () {
    window.print();
  });
  u(".date-utc").each(function (el) {
    var _el = u(el);
    _el.text(
      dayjs(_el.data("date")).local().format("YYYY-MM-DD [at] HH:mm:ss")
    );
  });
})();
