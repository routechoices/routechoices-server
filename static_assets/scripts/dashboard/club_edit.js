(function () {
  $("#id_admins").selectize({
    valueField: "id",
    labelField: "username",
    searchField: "username",
    multiple: true,
    create: false,
    plugins: ["preserve_on_blur"],
    load: function (query, callback) {
      if (!query.length || query.length < 2) return callback();
      reqwest({
        url: apiBaseUrl + "search/user?q=" + encodeURIComponent(query),
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
