(function () {
  u(".date-utc").each(function (el) {
    $el = u(el);
    $el.text(dayjs($el.data("date")).local().format("LLLL"));
  });
})();
