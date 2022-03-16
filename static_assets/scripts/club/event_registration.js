function selectizeDeviceInput() {
  $("select[name='device']").selectize({
    valueField: "id",
    labelField: "device_id",
    searchField: "device_id",
    multiple: true,
    create: false,
    plugins: ["preserve_on_blur"],
    load: function (query, callback) {
      if (!query.length || query.length < 4) {
        return callback();
      }
      reqwest({
        url: apiBaseUrl + "search/device?q=" + encodeURIComponent(query),
        method: "get",
        type: "json",
        withCredentials: true,
        crossOrigin: true,
        success: function (res) {
          callback(res.results);
        },
        error: function () {
          callback();
        },
      });
    },
  });
}

(function () {
  u(".date-utc").each(function (i, el) {
    var _el = u(el);
    _el.text(
      dayjs(_el.data("date")).local().format("MMMM D, YYYY [at] HH:mm:ss")
    );
  });
  selectizeDeviceInput();
})();
