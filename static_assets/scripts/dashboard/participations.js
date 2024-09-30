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
  u(".upload-btn").removeClass("disabled");
}

let route = {};

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

(function () {
  var thisUrl = window.location.href;
  if (
    thisUrl.includes("name-edited=1") ||
    thisUrl.includes("route-uploaded=1")
  ) {
    window.history.pushState("-", null, window.location.pathname);
  }

  const editModal = new bootstrap.Modal(
    document.getElementById("editNameModal")
  );
  const uploadModal = new bootstrap.Modal(
    document.getElementById("uploadRouteModal")
  );
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

  u(".edit-name-btn").on("click", function (e) {
    const el = u(e.target);
    u("#id_name").val(el.attr("data-competitor-name"));
    u("#id_short_name").val(el.attr("data-competitor-short-name"));
    u("#id_id").val(el.attr("data-competitor-id"));
    editModal.show();
  });

  u(".open-upload-btn").on("click", function (e) {
    const el = u(e.target);
    u("#id_competitor_aid").val(el.attr("data-competitor-id"));
    u("#id_gpx_file").val("");
    uploadModal.show();
  });

  u("#name-form").on("submit", function (e) {
    e.preventDefault();
    const name = u("#id_name").val();
    const shortName = u("#id_short_name").val();
    const competitorId = u("#id_id").val();
    reqwest({
      url: window.local.apiBaseUrl + "competitors/" + competitorId,
      method: "PATCH",
      withCredentials: true,
      crossOrigin: true,
      headers: {
        "X-CSRFToken": window.local.csrfToken,
      },
      data: {
        name,
        short_name: shortName,
      },
      success: () => {
        window.location.href = window.location.href + "?name-edited=1";
      },
      error: (e) => {
        swal({
          text: "Something went wrong",
          title: "error",
          type: "error",
        });
      },
    });
  });

  u("#upload-form").on("submit", function (e) {
    e.preventDefault();
    u(".upload-btn").addClass("disabled");
    var cmp_aid = u("#id_competitor_aid").val();
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
})();
