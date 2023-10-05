function onGPXLoaded(e) {
  const xml = e.target.result;
  let parsedGpx;
  try {
    parsedGpx = parseGpx(xml);
  } catch (e) {
    swal({
      text: "Error parsing your GPX file!",
      title: "error",
      type: "error",
    });
    return;
  }
  const newRoute = [];
  if (parsedGpx.segments.length === 0) {
    onRouteLoaded(newRoute);
    return;
  }
  for (let i = 0; i < parsedGpx.segments[0].length; i++) {
    const pos = parsedGpx.segments[0][i];
    if (pos.loc[0] && pos.time) {
      newRoute.push({ time: pos.time, latLon: [pos.loc[0], pos.loc[1]] });
    }
  }
  onRouteLoaded(newRoute);
}

function onRouteLoaded(newRoute) {
  if (!newRoute?.length) {
    swal({
      text: "Error parsing your file! No GPS points detected!",
      title: "error",
      type: "error",
    });
    return;
  }
  var ts = newRoute
    .map(function (pt) {
      return Math.round(+pt.time / 1e3);
    })
    .join(",");
  var lats = newRoute
    .map(function (pt) {
      return +pt.latLon[0];
    })
    .join(",");
  var lons = newRoute
    .map(function (pt) {
      return +pt.latLon[1];
    })
    .join(",");
  route = { timestamps: ts, latitudes: lats, longitudes: lons };
}

route = {};

function getGpxData(node, result) {
  if (!result) {
    result = { segments: [] };
  }
  switch (node.nodeName) {
    case "name":
      result.name = node.textContent;
      break;
    case "trkseg":
      var segment = [];
      result.segments.push(segment);
      for (let i = 0; i < node.childNodes.length; i++) {
        var snode = node.childNodes[i];
        if (snode.nodeName === "trkpt") {
          var trkpt = {
            loc: [
              parseFloat(snode.attributes["lat"].value),
              parseFloat(snode.attributes["lon"].value),
            ],
          };
          for (var j = 0; j < snode.childNodes.length; j++) {
            var ssnode = snode.childNodes[j];
            if (ssnode.nodeName === "time") {
              trkpt.time = new Date(ssnode.childNodes[0].data);
            }
          }
          segment.push(trkpt);
        }
      }
      break;
    default:
      break;
  }
  for (let i = 0; i < node.childNodes.length; i++) {
    getGpxData(node.childNodes[i], result);
  }
  return result;
}

function parseGpx(xmlstr) {
  if (typeof DOMParser == "undefined") {
    function DOMParser() {}
    DOMParser.prototype.parseFromString = function (str, contentType) {
      if (typeof XMLHttpRequest != "undefined") {
        var xmldata = new XMLHttpRequest();
        if (!contentType) {
          contentType = "application/xml";
        }
        xmldata.open(
          "GET",
          "data:" + contentType + ";charset=utf-8," + encodeURIComponent(str),
          false
        );
        if (xmldata.overrideMimeType) {
          xmldata.overrideMimeType(contentType);
        }
        xmldata.send(null);
        return xmldata.responseXML;
      }
    };
  }
  var doc = new DOMParser().parseFromString(xmlstr, "text/xml");
  return getGpxData(doc.documentElement);
}

function selectizeDeviceInput() {
  new TomSelect("select[name='device_id']", {
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
}

(function () {
  var thisUrl = window.location.href;
  if (
    thisUrl.includes("competitor-added=1") ||
    thisUrl.includes("route-uploaded=1")
  ) {
    window.history.pushState("-", null, window.location.pathname);
  }

  u(".date-utc").each(function (el) {
    var _el = u(el);
    _el.text(
      dayjs(_el.data("date")).local().format("MMMM D, YYYY [at] HH:mm:ss")
    );
  });

  if (u("#registration-form").nodes.length) {
    u("#registration-form").on("submit", function (e) {
      e.preventDefault();
      var formData = new FormData(e.target);
      var data = {
        name: formData.get("name"),
        short_name: formData.get("short_name"),
      };
      if (formData.get("device_id")) {
        data.device_id = u(
          '#id_device_id > option[value="' + formData.get("device_id") + '"]'
        ).text();
      }
      reqwest({
        url:
          window.local.apiBaseUrl +
          "events/" +
          window.local.eventId +
          "/register",
        method: "post",
        type: "json",
        withCredentials: true,
        crossOrigin: true,
        data: data,
        headers: {
          "X-CSRFToken": window.local.csrfToken,
        },
        success: function () {
          window.location.href = window.location.href + "?competitor-added=1";
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
    if (window.local.eventEnded) {
      u("#id_device_id").parent().remove();
    } else {
      selectizeDeviceInput();
      u("select[name='device_id']").on("change", function (e) {
        if (e.target.value) {
          u("#warning-if-device-id").removeClass("d-none");
        }
      });
    }
    if (u("#upload-form").nodes.length) {
      u("#id_device_id-ts-label").text(
        "Device ID (Leave blank if you want to upload a GPX File)"
      );
    }
  }

  if (u("#id_gpx_file").nodes.length) {
    u("#id_gpx_file").attr("accept", ".gpx");
    u("#id_gpx_file").on("change", function (e) {
      if (this.files.length > 0 && this.files[0].size > 2 * 1e7) {
        swal({
          title: "Error!",
          text: "File is too big!",
          type: "error",
          confirmButtonText: "OK",
        });
        this.value = "";
        return;
      }
      if (this.files.length > 0) {
        var reader = new FileReader();
        reader.onload = onGPXLoaded;
        reader.readAsText(this.files[0]);
      }
    });
  }

  if (u("#upload-form").nodes.length) {
    u("#upload-form").on("submit", function (e) {
      e.preventDefault();
      var formData = new FormData(e.target);
      var cmp_aid = formData.get("competitor_aid");
      reqwest({
        url: window.local.apiBaseUrl + "competitors/" + cmp_aid + "/route",
        method: "post",
        type: "json",
        withCredentials: true,
        crossOrigin: true,
        data: route,
        headers: {
          "X-CSRFToken": window.local.csrfToken,
        },
        success: function () {
          window.location.href = window.location.href + "?route-uploaded=1";
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
    if (
      u("#upload-form").find("#id_competitor_aid").nodes[0].options.length === 0
    ) {
      u("#upload-form").html(
        "<h3 style='color:rgb(0,0,0,0.6)'>No competitors to upload data to.</h3>"
      );
    }
  }
})();
