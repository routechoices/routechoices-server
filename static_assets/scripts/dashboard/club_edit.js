$(function () {
  $("#id_admins").selectize({
    valueField: "id",
    labelField: "username",
    searchField: "username",
    multiple: true,
    create: false,
    plugins: ["preserve_on_blur"],
    load: function (query, callback) {
      if (!query.length || query.length < 2) return callback();
      $.ajax({
        url: apiBaseUrl + "search/user?q=" + encodeURIComponent(query),
        type: "GET",
        xhrFields: {
          withCredentials: true,
        },
        crossDomain: true,
        error: function () {
          callback();
        },
        success: function (res) {
          callback(res.results);
        },
      });
    },
  });
});
