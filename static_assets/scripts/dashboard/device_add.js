(function () {
  new TomSelect("#id_device", {
    valueField: "id",
    labelField: "device_id",
    searchField: "device_id",
    create: true,
    createOnBlur: true,
    persist: false,
    plugins: ["preserve_on_blur"],
    load: function (query, callback) {
      if (query.length < 4) {
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
})();
