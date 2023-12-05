(function () {
  var tsDevId = null;
  function selectizeDeviceInput() {
    tsDevId = new TomSelect("select[name='device_id']", {
      valueField: "device_id",
      labelField: "device_id",
      searchField: "device_id",
      create: false,
      createOnBlur: false,
      persist: false,
      plugins: ["preserve_on_blur"],
      load: function (query, callback) {
        if (query.length < 4) {
          return callback();
        }
        reqwest({
          url:
            window.local.apiBaseUrl +
            "search/device?q=" +
            encodeURIComponent(query),
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

  u("#quick-creation-form").on("submit", function (e) {
    e.preventDefault();
    var now = dayjs();
    var formData = new FormData(e.target);
    var data = {
      name: "Quick tracking " + dayjs().local().format("YYYY-MM-DD HH:mm:ss"),
      club_slug: window.local.clubSlug,
      backdrop: formData.get("backdrop"),
      start_date: now.toISOString(),
      end_date: now
        .add(parseInt(formData.get("duration"), 10), "m")
        .toISOString(),
    };
    reqwest({
      url: window.local.apiBaseUrl + "events/",
      method: "post",
      type: "json",
      withCredentials: true,
      crossOrigin: true,
      data: data,
      headers: {
        "X-CSRFToken": window.local.csrfToken,
      },
      success: function (res) {
        reqwest({
          url: window.local.apiBaseUrl + "events/" + res.id + "/register",
          method: "post",
          type: "json",
          withCredentials: true,
          crossOrigin: true,
          data: {
            name: formData.get("name"),
            device_id: formData.get("device_id"),
          },
          headers: {
            "X-CSRFToken": window.local.csrfToken,
          },
          success: function () {
            window.localStorage.setItem(
              "quick-event-devId",
              formData.get("device_id")
            );
            window.location.href = res.url;
          },
          error: function (err) {
            if (err.status == 400) {
              swal({
                text: JSON.parse(err.responseText).join("\n"),
                title: "error",
                type: "error",
              });
            } else {
              swal({
                text: "Something went wrong",
                title: "error",
                type: "error",
              });
            }
          },
        });
      },
      error: function (err) {
        if (err.status == 400) {
          swal({
            text: JSON.parse(err.responseText).join("\n"),
            title: "error",
            type: "error",
          });
        } else {
          swal({
            text: "Something went wrong",
            title: "error",
            type: "error",
          });
        }
      },
    });
  });
  selectizeDeviceInput();
  u("#id_device_id").attr("required", true);
  u("#id_name").val(window.local.username);
  var myUrl = new URL(window.location.href.replace(/#/g, "?"));
  var urlDevId = myUrl.searchParams.get("device_id");
  var devId = urlDevId || window.localStorage.getItem("quick-event-devId");
  if (devId) {
    tsDevId.load(devId, function (res) {
      if (res) {
        tsDevId.setValue(devId);
      }
    });
  }
})();
