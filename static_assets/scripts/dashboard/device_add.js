function displayErrors(err) {
  u("#importErrors")
    .text(err)
    .css({ display: "block", "white-space": "pre-line" });
}

function displaySuccess(msg) {
  u("#importSuccess").text(msg).css({ display: "block" });
}

function onCsvParsed(result) {
  u("#csv_input").val("");
  displayErrors("");
  var nImported = 0;
  var errors = "";
  if (result.errors.length > 0) {
    errors = "No lines found";
  }
  if (!errors) {
    result.data.forEach(function (l) {
      if (l.length == 1 && l[0] == "") {
        return; // empty line
      }
      if (l.length != 2) {
        errors += "All rows should have 2 columns\n";
      } else {
        var imeiOrDeviceId = l[0];
        var nickname = l[1];
        if (nickname.length > 12) {
          errors +=
            "IMEI or DeviceID " +
            imeiOrDeviceId +
            ', nickname "' +
            nickname +
            '": nickname too long (Max 12 characters)\n';
          return;
        }
        if (imeiOrDeviceId.length === 8) {
          var deviceId = imeiOrDeviceId;
          reqwest({
            url:
              window.local.apiBaseUrl +
              "clubs/" +
              window.local.clubSlug +
              "/devices/" +
              deviceId +
              "/",
            method: "patch",
            data: {
              nickname: nickname,
            },
            headers: { "X-CSRFToken": window.local.csrfToken },
            type: "json",
            withCredentials: true,
            crossOrigin: true,
          })
            .then(function () {
              nImported++;
              displaySuccess(nImported + " devices imported");
            })
            .fail(function () {
              errors +=
                "Device ID " +
                deviceId +
                ', nickname "' +
                nickname +
                '": Failed\n';
              displayErrors(errors);
            });
        } else {
          var imei = imeiOrDeviceId;
          reqwest({
            url: window.local.apiBaseUrl + "device/",
            method: "post",
            data: {
              imei: imei,
              csrfmiddlewaretoken: window.local.csrfToken,
            },
            type: "json",
            withCredentials: true,
            crossOrigin: true,
          })
            .then(function (resp) {
              var deviceId = resp.device_id;
              reqwest({
                url:
                  window.local.apiBaseUrl +
                  "clubs/" +
                  window.local.clubSlug +
                  "/devices/" +
                  deviceId +
                  "/",
                method: "patch",
                data: {
                  nickname: nickname,
                },
                headers: { "X-CSRFToken": window.local.csrfToken },
                type: "json",
                withCredentials: true,
                crossOrigin: true,
              })
                .then(function () {
                  nImported++;
                  displaySuccess(nImported + " devices imported");
                })
                .fail(function () {
                  errors +=
                    "IMEI " + imei + ', nickname "' + nickname + '": Failed\n';
                  displayErrors(errors);
                });
            })
            .fail(function () {
              errors +=
                "IMEI " +
                imei +
                ', nickname "' +
                nickname +
                '": Invalid IMEI\n';
            });
        }
      }
    });
  }
  if (errors) {
    displayErrors(errors);
  }
}

(function () {
  new TomSelect("#id_device", {
    valueField: "id",
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

  u("#importCSVImei").on("submit", function (e) {
    e.preventDefault();
    Papa.parse(u("#csv_input").nodes[0].files[0], {
      complete: onCsvParsed,
      delimiter: ";",
    });
  });
})();
