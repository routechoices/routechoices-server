SpheroidProjection = (function () {
  var p = "prototype",
    m = Math,
    pi = m.PI,
    _180 = 180.0,
    rad = 6378137,
    originShift = pi * rad,
    pi_180 = pi / _180;
  function S() {}
  S[p].latlng_to_meters = function (latlng) {
    return {
      x: latlng.lng * rad * pi_180,
      y: m.log(m.tan(((90 + latlng.lat) * pi_180) / 2)) * rad,
    };
  };
  S[p].meters_to_latlng = function (mxy) {
    return {
      lat: (2 * m.atan(m.exp(mxy.y / rad)) - pi / 2) / pi_180,
      lng: mxy.x / rad / pi_180,
    };
  };
  S[p].resolution = function (zoom) {
    return (2 * originShift) / (256 * m.pow(2, zoom));
  };
  S[p].zoom_for_pixel_size = function (pixelSize) {
    for (i = 0; i < 30; i++) {
      if (pixelSize > resolution(i)) {
        return m.max(i - 1, 0);
      }
    }
  };
  S[p].pixels_to_meters = function (px, py, zoom) {
    var res = resolution(zoom),
      mx = px * res - originShift,
      my = py * res - originShift;
    return { x: mx, y: my };
  };
  return S;
})();

function adj(m) {
  // Compute the adjugate of m
  return [
    m[4] * m[8] - m[5] * m[7],
    m[2] * m[7] - m[1] * m[8],
    m[1] * m[5] - m[2] * m[4],
    m[5] * m[6] - m[3] * m[8],
    m[0] * m[8] - m[2] * m[6],
    m[2] * m[3] - m[0] * m[5],
    m[3] * m[7] - m[4] * m[6],
    m[1] * m[6] - m[0] * m[7],
    m[0] * m[4] - m[1] * m[3],
  ];
}

function multmm(a, b) {
  // multiply two matrices
  var c = Array(9);
  for (var i = 0; i !== 3; ++i) {
    for (var j = 0; j !== 3; ++j) {
      var cij = 0;
      for (var k = 0; k !== 3; ++k) {
        cij += a[3 * i + k] * b[3 * k + j];
      }
      c[3 * i + j] = cij;
    }
  }
  return c;
}

function multmv(m, v) {
  // multiply matrix and vector
  return [
    m[0] * v[0] + m[1] * v[1] + m[2] * v[2],
    m[3] * v[0] + m[4] * v[1] + m[5] * v[2],
    m[6] * v[0] + m[7] * v[1] + m[8] * v[2],
  ];
}

function basisToPoints(x1, y1, x2, y2, x3, y3, x4, y4) {
  var m = [x1, x2, x3, y1, y2, y3, 1, 1, 1];
  var v = multmv(adj(m), [x4, y4, 1]);
  return multmm(m, [v[0], 0, 0, 0, v[1], 0, 0, 0, v[2]]);
}

function general2DProjection(
  x1s,
  y1s,
  x1d,
  y1d,
  x2s,
  y2s,
  x2d,
  y2d,
  x3s,
  y3s,
  x3d,
  y3d,
  x4s,
  y4s,
  x4d,
  y4d
) {
  var s = basisToPoints(x1s, y1s, x2s, y2s, x3s, y3s, x4s, y4s);
  var d = basisToPoints(x1d, y1d, x2d, y2d, x3d, y3d, x4d, y4d);
  return multmm(d, adj(s));
}

function project(m, x, y) {
  var v = multmv(m, [x, y, 1]);
  return [v[0] / v[2], v[1] / v[2]];
}

(function () {
  var map_a = null;
  var map_b = null;
  var map_c = null;
  var markers_a = [];
  var markers_b = [];
  var raster_map_image;
  var corners_latlng = [];
  var calib_string = null;
  var icon_scale = browser.mobile ? 2 : 1;
  var icons = [
    color_icon("blue"),
    color_icon("red"),
    color_icon("green"),
    color_icon("orange"),
  ];
  var help_texts = [
    "Select 4 distincts points on the raster map and on the world map.",
    "Check that the raster map is aligned with the world map.",
  ];

  L.TileLayer.Common = L.TileLayer.extend({
    initialize: function (options) {
      L.TileLayer.prototype.initialize.call(this, this.url, options);
    },
  });
  L.TileLayer["osm"] = L.TileLayer.Common.extend({
    url: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    options: { attribution: "&copy; OpenStreetMap contributors" },
  });
  L.TileLayer["gmap-street"] = L.TileLayer.Common.extend({
    url: "https://mt0.google.com/vt/x={x}&y={y}&z={z}",
    options: { attribution: "&copy; Google" },
  });
  L.TileLayer["gmap-hybrid"] = L.TileLayer.Common.extend({
    url: "https://mt0.google.com/vt/lyrs=y&hl=en&x={x}&y={y}&z={z}",
    options: { attribution: "&copy; Google" },
  });
  L.TileLayer["finland-topo"] = L.TileLayer.Common.extend({
    url: "https://tiles.kartat.kapsi.fi/peruskartta/{z}/{x}/{y}.jpg",
    options: { attribution: "&copy; National Land Survey of Finland" },
  });
  L.TileLayer["mapant-fi"] = L.TileLayer.Common.extend({
    url: "https://wmts.mapant.fi/wmts_EPSG3857.php?z={z}&x={x}&y={y}",
    options: {
      attribution: "&copy; MapAnt and National Land Survey of Finland",
    },
  });
  L.TileLayer["norway-topo"] = L.TileLayer.Common.extend({
    url: "https://opencache.statkart.no/gatekeeper/gk/gk.open_gmaps?layers=topo4&zoom={z}&x={x}&y={y}",
    options: { attribution: "" },
  });
  L.TileLayer["world-topo"] = L.TileLayer.Common.extend({
    url: "https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",
    options: { attribution: "&copy; OpenTopoMap (CC-BY-SA)" },
  });
  L.TileLayer["mapant-no"] = L.TileLayer.Common.extend({
    url: "https://mapant.no/osm-tiles/{z}/{x}/{y}.png",
    options: { attribution: "&copy; MapAnt.no" },
  });
  L.TileLayer["mapant-es"] = L.tileLayer.wms(
    "https://mapant.es/mapserv?map=/mapas/geotiff.map",
    {
      layers: "geotiff",
      format: "image/png",
      version: "1.3.0",
      transparent: true,
    }
  );

  function color_icon(color) {
    return new L.Icon({
      iconUrl:
        "/static/vendor/leaflet-color-markers-1.0.0/img/marker-icon-2x-" +
        color +
        ".png",
      shadowUrl:
        "/static/vendor/leaflet-color-markers-1.0.0/img/marker-shadow.png",
      iconSize: [25 * icon_scale, 41 * icon_scale],
      iconAnchor: [12 * icon_scale, 41 * icon_scale],
      popupAnchor: [1 * icon_scale, -34 * icon_scale],
      shadowSize: [41 * icon_scale, 41 * icon_scale],
    });
  }

  function resetOrientation(src, callback) {
    loadImage(
      src,
      function (d) {
        callback(d.toDataURL("image/jpeg", 0.4));
      },
      { orientation: 1 }
    );
  }

  function loadMapImage() {
    var imageInput = window.opener.document.querySelector("#id_image");
    var imageURL = u(imageInput).parent().find("a").attr("href");
    if (imageInput.files && imageInput.files[0]) {
      var fr = new FileReader();
      fr.onload = function (e) {
        resetOrientation(e.target.result, function (imgDataURI) {
          var img = new Image();
          img.onload = function () {
            u("#help_text").text(help_texts[0]);
            display_raster_map(img);
            display_world_map();
          };
          img.src = imgDataURI;
        });
      };
      fr.readAsDataURL(imageInput.files[0]);
    } else if (imageURL) {
      var img = new Image();
      img.addEventListener("load", function () {
        u("#help_text").text(help_texts[0]);
        display_raster_map(img);
        display_world_map();
      });
      img.src = imageURL;
    } else {
      window.close();
    }
  }

  function display_raster_map(image) {
    map_a = L.map("raster_map", { crs: L.CRS.Simple, minZoom: -5, maxZoom: 2 });
    var bounds = [
      map_a.unproject([0, 0]),
      map_a.unproject([image.width, image.height]),
    ];
    L.imageOverlay(image.src, bounds).addTo(map_a);
    map_a.fitBounds(bounds);
    raster_map_image = image;
    map_a.on("click", function (e) {
      set_ref_pts_a(map_a.project(e.latlng, 0));
    });
  }
  function display_world_map() {
    map_b = L.map("tile_map").setView([0, 0], 2);
    L.Control.geocoder({
      defaultMarkGeocode: false,
    })
      .on("markgeocode", function (e) {
        var bbox = e.geocode.bbox;
        map_b.fitBounds(bbox);
      })
      .addTo(map_b);
    var baseLayers = {};
    var defaultLayer = new L.TileLayer["osm"]();
    baseLayers["Open Street Map"] = defaultLayer;
    baseLayers["Google Map Street"] = new L.TileLayer["gmap-street"]();
    baseLayers["Google Map Satellite"] = new L.TileLayer["gmap-hybrid"]();
    baseLayers["Mapant Finland"] = new L.TileLayer["mapant-fi"]();
    baseLayers["Mapant Norway"] = new L.TileLayer["mapant-no"]();
    baseLayers["Mapant Spain"] = L.TileLayer["mapant-es"];
    baseLayers["Topo Finland"] = new L.TileLayer["finland-topo"]();
    baseLayers["Topo Norway"] = new L.TileLayer["norway-topo"]();
    baseLayers["Topo World"] = new L.TileLayer["world-topo"]();

    map_b.addLayer(defaultLayer);
    map_b.addControl(new L.Control.Layers(baseLayers));
    map_b.on("click", function (e) {
      set_ref_pts_b(e.latlng);
    });
  }
  function display_preview_map() {
    var bounds = corners_latlng;
    map_c = L.map("preview_map").fitBounds(bounds);
    var transformedImage = L.imageTransform(raster_map_image.src, bounds, {
      opacity: 0.7,
    });
    transformedImage.addTo(map_c);

    var baseLayers = {};
    var defaultLayer = new L.TileLayer["osm"]();
    baseLayers["Open Street Map"] = defaultLayer;
    baseLayers["Google Map Street"] = new L.TileLayer["gmap-street"]();
    baseLayers["Google Map Satellite"] = new L.TileLayer["gmap-hybrid"]();
    baseLayers["Mapant Finland"] = new L.TileLayer["mapant-fi"]();
    baseLayers["Mapant Norway"] = new L.TileLayer["mapant-no"]();
    baseLayers["Mapant Spain"] = L.TileLayer["mapant-es"];
    baseLayers["Topo Finland"] = new L.TileLayer["finland-topo"]();
    baseLayers["Topo Norway"] = new L.TileLayer["norway-topo"]();
    baseLayers["Topo World"] = new L.TileLayer["world-topo"]();

    map_c.addLayer(defaultLayer);
    map_c.addControl(
      new L.Control.Layers(baseLayers, { Map: transformedImage })
    );
  }

  function set_ref_pts_a(xy) {
    if (markers_a.length < 4) {
      var marker = L.marker(map_a.unproject(xy, 0), {
        icon: icons[markers_a.length],
        draggable: "true",
      }).addTo(map_a);
      markers_a.push(marker);
      check_calib();
    }
  }

  function set_ref_pts_b(latlng) {
    if (markers_b.length < 4) {
      var marker = L.marker(latlng, {
        icon: icons[markers_b.length],
        draggable: "true",
      }).addTo(map_b);
      markers_b.push(marker);
      check_calib();
    }
  }

  function check_calib() {
    if (markers_a.length == 4 && markers_b.length == 4) {
      u("#to_step3_button").removeClass("disabled");
    } else {
      u("#to_step3_button").addClass("disabled");
    }
  }

  function compute_calib_string() {
    var xy_a = [];
    var xy_b = [];
    var proj = new SpheroidProjection();
    for (var i = 0; i < markers_a.length; i++) {
      xy_a[i] = map_a.project(markers_a[i].getLatLng(), 0);
    }
    for (var i = 0; i < markers_b.length; i++) {
      xy_b[i] = proj.latlng_to_meters(markers_b[i].getLatLng());
    }
    var matrix3d = general2DProjection(
      xy_a[0].x,
      xy_a[0].y,
      xy_b[0].x,
      xy_b[0].y,
      xy_a[1].x,
      xy_a[1].y,
      xy_b[1].x,
      xy_b[1].y,
      xy_a[2].x,
      xy_a[2].y,
      xy_b[2].x,
      xy_b[2].y,
      xy_a[3].x,
      xy_a[3].y,
      xy_b[3].x,
      xy_b[3].y
    );
    var corners_m = [
      project(matrix3d, 0, 0),
      project(matrix3d, raster_map_image.width, 0),
      project(matrix3d, raster_map_image.width, raster_map_image.height),
      project(matrix3d, 0, raster_map_image.height),
    ];
    for (var i = 0; i < corners_m.length; i++) {
      corners_latlng[i] = proj.meters_to_latlng({
        x: corners_m[i][0],
        y: corners_m[i][1],
      });
    }
    build_calib_string(corners_latlng);
  }

  function round5(x) {
    return Math.round(x * 1e5) / 1e5;
  }

  function build_calib_string(c) {
    var parts = [];
    for (var i = 0; i < c.length; i++) {
      parts.push(round5(c[i].lat) + "," + round5(c[i].lng));
    }
    calib_string = parts.join(",");
  }

  u("#reset_raster_markers_button").on("click", function (e) {
    e.preventDefault();
    for (var i = 0; i < markers_a.length; i++) {
      markers_a[i].remove();
    }
    markers_a = [];

    u("#to_step3_button").addClass("disabled");
  });

  u("#reset_world_markers_button").on("click", function (e) {
    e.preventDefault();
    for (var i = 0; i < markers_b.length; i++) {
      markers_b[i].remove();
    }
    markers_b = [];

    u("#to_step3_button").addClass("disabled");
  });
  u("#to_step3_button").on("click", function (e) {
    e.preventDefault();
    compute_calib_string();
    u("#step2").addClass("d-none");
    u("#step3").removeClass("d-none");
    u("#help_text").text(help_texts[1]);
    display_preview_map();
  });
  u("#back_step2_button").on("click", function (e) {
    e.preventDefault();
    map_c.remove();
    u("#help_text").text(help_texts[0]);
    u("#step3").addClass("d-none");
    u("#step2").removeClass("d-none");
  });

  u("#to_step4_button").on("click", function (e) {
    e.preventDefault();
    var el = window.opener.document.querySelector("#id_corners_coordinates");
    el.value = calib_string;
    var event = document.createEvent("Event");
    event.initEvent("input", true, true);
    el.dispatchEvent(event);
    window.close();
  });
  if (!window.opener) {
    window.location.href = "/";
  } else {
    loadMapImage();
  }
})();
