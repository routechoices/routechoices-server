(function () {
  $("#id_device").selectize({
    valueField: "id",
    labelField: "device_id",
    searchField: "device_id",
    multiple: true,
    create: false,
    plugins: ["preserve_on_blur"],
    load: function (query, callback) {
      if (!query.length || query.length < 4) return callback();
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
})();
