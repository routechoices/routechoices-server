pdfjsLib.GlobalWorkerOptions.workerSrc =
  "//www.routechoices.com/static/vendor/pdfjs-2.7.570/pdf.worker.min.js";

function cloneOptions(options) {
  var ret = {};
  for (var i in options) {
    var item = options[i];
    if (item && item.clone) {
      ret[i] = item.clone();
    } else if (item instanceof L.Layer) {
      ret[i] = cloneLayer(item);
    } else {
      ret[i] = item;
    }
  }
  return ret;
}

function cloneInnerLayers(layer) {
  var layers = [];
  layer.eachLayer(function (inner) {
    layers.push(cloneLayer(inner));
  });
  return layers;
}

function cloneLayer(layer) {
  var options = cloneOptions(layer.options);

  // we need to test for the most specific class first, i.e.
  // Circle before CircleMarker

  // Renderers
  if (layer instanceof L.SVG) {
    return L.svg(options);
  }
  if (layer instanceof L.Canvas) {
    return L.canvas(options);
  }

  // GoogleMutant GridLayer
  if (L.GridLayer.GoogleMutant && layer instanceof L.GridLayer.GoogleMutant) {
    var googleLayer = L.gridLayer.googleMutant(options);

    layer._GAPIPromise.then(function () {
      var subLayers = Object.keys(layer._subLayers);

      for (var i in subLayers) {
        googleLayer.addGoogleLayer(subLayers[i]);
      }
    });

    return googleLayer;
  }

  // Tile layers
  if (layer instanceof L.TileLayer.WMS) {
    return L.tileLayer.wms(layer._url, options);
  }
  if (layer instanceof L.TileLayer) {
    return L.tileLayer(layer._url, options);
  }
  if (layer instanceof L.ImageOverlay) {
    return L.imageOverlay(layer._url, layer._bounds, options);
  }

  // Marker layers
  if (layer instanceof L.Marker) {
    return L.marker(layer.getLatLng(), options);
  }

  if (layer instanceof L.Circle) {
    return L.circle(layer.getLatLng(), layer.getRadius(), options);
  }
  if (layer instanceof L.CircleMarker) {
    return L.circleMarker(layer.getLatLng(), options);
  }

  if (layer instanceof L.Rectangle) {
    return L.rectangle(layer.getBounds(), options);
  }
  if (layer instanceof L.Polygon) {
    return L.polygon(layer.getLatLngs(), options);
  }
  if (layer instanceof L.Polyline) {
    return L.polyline(layer.getLatLngs(), options);
  }

  if (layer instanceof L.GeoJSON) {
    return L.geoJson(layer.toGeoJSON(), options);
  }

  if (layer instanceof L.FeatureGroup) {
    return L.featureGroup(cloneInnerLayers(layer));
  }
  if (layer instanceof L.LayerGroup) {
    return L.layerGroup(cloneInnerLayers(layer));
  }

  throw "Unknown layer, cannot clone this layer. Leaflet-version: " + L.version;
}

var extractCornersCoordsFromFilename = function (filename) {
  var re = /(_[-]?\d+(\.\d+)?){8}_\.(gif|png|jpg|jpeg|webp)$/;
  var found = filename.match(re);
  if (!found) {
    return false;
  } else {
    var coords = found[0].split("_");
    coords.pop();
    coords.shift();
    return coords.join(",");
  }
};
var onPDF = function (ev, filename) {
  var loadingTask = pdfjsLib.getDocument({
    data: new Uint8Array(ev.target.result),
  });
  loadingTask.promise.then(function (pdf) {
    pdf.getPage(1).then(function (page) {
      var PRINT_RESOLUTION = 300;
      var PRINT_UNITS = PRINT_RESOLUTION / 72.0;
      var CSS_UNITS = 96.0 / 72.0;
      var viewport = page.getViewport({ scale: 1 });
      var width = Math.floor(viewport.width * CSS_UNITS) + "px";
      var height = Math.floor(viewport.height * CSS_UNITS) + "px";

      // Prepare canvas using PDF page dimensions
      var canvas = document.createElement("canvas");
      canvas.height = Math.floor(viewport.height * PRINT_UNITS);
      canvas.width = Math.floor(viewport.width * PRINT_UNITS);
      var context = canvas.getContext("2d");
      // Render PDF page into canvas context
      var renderContext = {
        canvasContext: context,
        transform: [PRINT_UNITS, 0, 0, PRINT_UNITS, 0, 0],
        viewport: viewport,
      };
      var renderTask = page.render(renderContext);
      renderTask.promise.then(function () {
        var ext = filename.split(".").pop();
        filename = filename.slice(0, filename.length - ext.length) + "jpg";
        canvas.toBlob(
          function (blob) {
            var file = new File([blob], filename, {
              type: "image/jpeg",
              lastModified: new Date().getTime(),
            });
            var container = new DataTransfer();
            container.items.add(file);
            u("#id_image").nodes[0].files = container.files;
            u("#id_image").trigger("change");
          },
          "image/jpeg",
          0.8
        );
      });
    });
  });
};

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

var backdropMaps = {
  osm: L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution:
      'Map data &copy; <a href="http://openstreetmap.org">OpenStreetMap</a> contributors, <a href="http://creativecommons.org/licenses/by-sa/2.0/">CC-BY-SA</a>, Imagery © <a href="http://mapbox.com">Mapbox</a>',
    className: "wms256",
  }),
  "gmap-street": L.tileLayer("https://mt0.google.com/vt/x={x}&y={y}&z={z}", {
    attribution: "&copy; Google",
    className: "wms256",
  }),
  "gmap-hybrid": L.tileLayer(
    "https://mt0.google.com/vt/lyrs=y&hl=en&x={x}&y={y}&z={z}",
    {
      attribution: "&copy; Google",
      className: "wms256",
    }
  ),
  "topo-fi": L.tileLayer(
    "https://tiles.kartat.kapsi.fi/peruskartta/{z}/{x}/{y}.jpg",
    {
      attribution: "&copy; National Land Survey of Finland",
      className: "wms256",
    }
  ),
  "mapant-fi": L.tileLayer(
    "https://wmts.mapant.fi/wmts_EPSG3857.php?z={z}&x={x}&y={y}",
    {
      attribution: "&copy; MapAnt.fi and National Land Survey of Finland",
      className: "wms256",
    }
  ),
  "topo-no": L.tileLayer(
    "https://opencache.statkart.no/gatekeeper/gk/gk.open_gmaps?layers=topo4&zoom={z}&x={x}&y={y}",
    {
      attribution: "",
      className: "wms256",
    }
  ),
  "mapant-no": L.tileLayer("https://mapant.no/osm-tiles/{z}/{x}/{y}.png", {
    attribution: "&copy; MapAnt.no",
    className: "wms256",
  }),
  "mapant-es": L.tileLayer.wms("https://mapant.es/wms", {
    layers: "mapant.es",
    format: "image/png",
    version: "1.3.0",
    transparent: true,
    attribution: "&copy; MapAnt.es",
    className: "wms256",
  }),
  "topo-world": L.tileLayer("https://tile.opentopomap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenTopoMap (CC-BY-SA)",
    className: "wms256",
  }),
  "topo-world-alt": L.tileLayer(
    "https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}",
    {
      attribution: "&copy; ArcGIS Online",
      className: "wms256",
    }
  ),
};
(function () {
  function openCalibrationHelper() {
    u("#main").addClass("d-none");
    u("#calibration-helper").removeClass("d-none");
    markersRaster = [];
    markersWorld = [];
    cornersLatLng = [];
    calibString = null;
    loadMapImage();
  }

  function closeCalibrationHelper() {
    u("#calibration-helper").addClass("d-none");
    u("#main").removeClass("d-none");
  }

  function closePreview() {
    u("#calibration-viewer").addClass("d-none");
    u("#main").removeClass("d-none");
  }

  function resetImageOrientation(src, callback) {
    loadImage(
      src,
      function (d) {
        callback(d.toDataURL("image/png"));
      },
      { orientation: 1 }
    );
  }

  function loadMapImagePreview() {
    var imageInput = document.querySelector("#id_image");
    var imageURL = u(imageInput).parent().find("a").attr("href");
    if (imageInput.files && imageInput.files[0]) {
      var fr = new FileReader();
      fr.onload = function (e) {
        resetImageOrientation(e.target.result, function (imgDataURI) {
          var img = new Image();
          img.onload = function () {
            rasterMapImage = img;
            displayPreviewMap();
          };
          img.src = imgDataURI;
        });
      };
      fr.readAsDataURL(imageInput.files[0]);
    } else if (imageURL) {
      var img = new Image();
      img.addEventListener("load", function () {
        rasterMapImage = img;
        displayPreviewMap();
      });
      img.src = imageURL;
    } else {
      closePreview();
    }
  }

  function loadMapImage() {
    u("#calibration-help-text").text(calibHelpTexts[0]);
    displayWorldMap();
    if (rasterCalibMap) {
      rasterCalibMap.off();
      rasterCalibMap.remove();
      rasterCalibMap = null;
      u("#raster-map").html("");
    }

    var imageInput = document.querySelector("#id_image");
    var imageURL = u(imageInput).parent().find("a").attr("href");
    if (imageInput.files && imageInput.files[0]) {
      var fr = new FileReader();
      fr.onload = function (e) {
        resetImageOrientation(e.target.result, function (imgDataURI) {
          var img = new Image();
          img.onload = function () {
            displayRasterMap(img);
          };
          img.src = imgDataURI;
        });
      };
      fr.readAsDataURL(imageInput.files[0]);
    } else if (imageURL) {
      var img = new Image();
      img.onload = function () {
        displayRasterMap(img);
      };
      img.src = imageURL;
    } else {
      closeCalibrationHelper();
    }
  }

  function colorIcon(color) {
    return new L.Icon({
      iconUrl:
        "/static/vendor/leaflet-color-markers-1.0.0/img/marker-icon-2x-" +
        color +
        ".png",
      shadowUrl:
        "/static/vendor/leaflet-color-markers-1.0.0/img/marker-shadow.png",
      iconSize: [25 * iconScale, 41 * iconScale],
      iconAnchor: [12 * iconScale, 41 * iconScale],
      popupAnchor: [1 * iconScale, -34 * iconScale],
      shadowSize: [41 * iconScale, 41 * iconScale],
    });
  }

  function setRefPtsRaster(xy) {
    if (markersRaster.length < 4) {
      var marker = L.marker(rasterCalibMap.unproject(xy, 0), {
        icon: icons[markersRaster.length],
        draggable: "true",
      }).addTo(rasterCalibMap);
      markersRaster.push(marker);
      checkCalib();
      if (markersRaster.length === 4) {
        L.DomUtil.removeClass(rasterCalibMap._container, "crosshair-cursor");
      }
    }
  }

  function setRefPtsWorld(latlng) {
    if (markersWorld.length < 4) {
      var marker = L.marker(latlng, {
        icon: icons[markersWorld.length],
        draggable: "true",
      }).addTo(worldCalibMap);
      markersWorld.push(marker);
      checkCalib();
      if (markersWorld.length === 4) {
        L.DomUtil.removeClass(worldCalibMap._container, "crosshair-cursor");
      }
    }
  }

  function checkCalib() {
    if (markersWorld.length == 4 && markersRaster.length == 4) {
      u("#to-calibration-step-2-button").removeClass("disabled");
    } else {
      u("#to-calibration-step-2-button").addClass("disabled");
    }
  }

  function isValidCalibString(s) {
    return s.match(/^[-]?\d+(\.\d+)?(,[-]?\d+(\.\d+)?){7}$/);
  }

  function loadCalibString() {
    calibString = u("#id_corners_coordinates").val();
    if (!calibString || !isValidCalibString(calibString)) {
      closePreview();
    }
    var vals = calibString.split(",").map(function (x) {
      return parseFloat(x);
    });
    cornersLatLng = [
      { lat: vals[0], lng: vals[1] },
      { lat: vals[2], lng: vals[3] },
      { lat: vals[4], lng: vals[5] },
      { lat: vals[6], lng: vals[7] },
    ];
  }

  function displayRasterMap(image) {
    if (rasterCalibMap) {
      rasterCalibMap.off();
      rasterCalibMap.remove();
      rasterCalibMap = null;
      u("#raster-map").html("");
    }
    rasterCalibMap = L.map("raster-map", {
      crs: L.CRS.Simple,
      minZoom: -5,
      maxZoom: 2,
    });
    L.DomUtil.addClass(rasterCalibMap._container, "crosshair-cursor");
    var bounds = [
      rasterCalibMap.unproject([0, 0]),
      rasterCalibMap.unproject([image.width, image.height]),
    ];
    L.imageOverlay(image.src, bounds).addTo(rasterCalibMap);
    rasterCalibMap.fitBounds(bounds);
    rasterMapImage = image;
    rasterCalibMap.on("click", function (e) {
      setRefPtsRaster(rasterCalibMap.project(e.latlng, 0));
    });
  }

  function displayPreviewMap() {
    if (previewMap) {
      previewMap.off();
      previewMap.remove();
      previewMap = null;
      u("#test-map").html("");
    }
    previewMap = L.map("preview-map");

    var defaultLayer = cloneLayer(backdropMaps["osm"]);
    var baseLayers = {
      "Open Street Map": defaultLayer,
      "Google Map Street": cloneLayer(backdropMaps["gmap-street"]),
      "Google Map Satellite": cloneLayer(backdropMaps["gmap-hybrid"]),
      "Mapant Finland": cloneLayer(backdropMaps["mapant-fi"]),
      "Mapant Norway": cloneLayer(backdropMaps["mapant-no"]),
      "Mapant Spain": cloneLayer(backdropMaps["mapant-es"]),
      "Topo Finland": cloneLayer(backdropMaps["topo-fi"]),
      "Topo Norway": cloneLayer(backdropMaps["topo-no"]),
      "Topo World (OpenTopo)": cloneLayer(backdropMaps["topo-world"]),
      "Topo World (ArcGIS)": cloneLayer(backdropMaps["topo-world-alt"]),
    };

    previewMap.addLayer(defaultLayer);
    var bounds = cornersLatLng;

    var transformedImage = L.imageTransform(rasterMapImage.src, bounds, {
      opacity: 0.7,
    });
    transformedImage.addTo(previewMap);

    var controlLayers = L.control.layers(baseLayers, {
      Map: transformedImage,
    });
    previewMap.addControl(controlLayers);
    if (L.Browser.touch && L.Browser.mobile) {
      previewMap.on("baselayerchange", function (e) {
        controlLayers.collapse();
      });
    }

    previewMap.fitBounds(bounds);
  }

  function displayCalibPreviewMap() {
    if (previewCalibMap) {
      previewCalibMap.off();
      previewCalibMap.remove();
      previewCalibMap = null;
      u("#test-map").html("");
    }
    var bounds = cornersLatLng;
    previewCalibMap = L.map("test-map").fitBounds(bounds);
    var transformedImage = L.imageTransform(rasterMapImage.src, bounds, {
      opacity: 0.7,
    });
    transformedImage.addTo(previewCalibMap);

    var defaultLayer = cloneLayer(backdropMaps["osm"]);
    var baseLayers = {
      "Open Street Map": defaultLayer,
      "Google Map Street": cloneLayer(backdropMaps["gmap-street"]),
      "Google Map Satellite": cloneLayer(backdropMaps["gmap-hybrid"]),
      "Mapant Finland": cloneLayer(backdropMaps["mapant-fi"]),
      "Mapant Norway": cloneLayer(backdropMaps["mapant-no"]),
      "Mapant Spain": cloneLayer(backdropMaps["mapant-es"]),
      "Topo Finland": cloneLayer(backdropMaps["topo-fi"]),
      "Topo Norway": cloneLayer(backdropMaps["topo-no"]),
      "Topo World (OpenTopo)": cloneLayer(backdropMaps["topo-world"]),
      "Topo World (ArcGIS)": cloneLayer(backdropMaps["topo-world-alt"]),
    };

    var controlLayersPrev = L.control.layers(baseLayers, {
      Map: transformedImage,
    });
    previewCalibMap.addLayer(defaultLayer);
    previewCalibMap.addControl(controlLayersPrev);
    if (L.Browser.touch && L.Browser.mobile) {
      previewCalibMap.on("baselayerchange", function (e) {
        controlLayersPrev.collapse();
      });
    }
    previewCalibMap.invalidateSize();
  }

  function displayWorldMap() {
    if (worldCalibMap) {
      worldCalibMap.off();
      worldCalibMap.remove();
      worldCalibMap = null;
      u("#world-map").html("");
    }
    worldCalibMap = L.map("world-map").setView([0, 0], 2);
    L.DomUtil.addClass(worldCalibMap._container, "crosshair-cursor");
    L.Control.geocoder({
      defaultMarkGeocode: false,
    })
      .on("markgeocode", function (e) {
        var bbox = e.geocode.bbox;
        worldCalibMap.fitBounds(bbox);
      })
      .addTo(worldCalibMap);
    var defaultLayer = cloneLayer(backdropMaps["osm"]);
    var baseLayers = {
      "Open Street Map": defaultLayer,
      "Google Map Street": cloneLayer(backdropMaps["gmap-street"]),
      "Google Map Satellite": cloneLayer(backdropMaps["gmap-hybrid"]),
      "Mapant Finland": cloneLayer(backdropMaps["mapant-fi"]),
      "Mapant Norway": cloneLayer(backdropMaps["mapant-no"]),
      "Mapant Spain": cloneLayer(backdropMaps["mapant-es"]),
      "Topo Finland": cloneLayer(backdropMaps["topo-fi"]),
      "Topo Norway": cloneLayer(backdropMaps["topo-no"]),
      "Topo World (OpenTopo)": cloneLayer(backdropMaps["topo-world"]),
      "Topo World (ArcGIS)": cloneLayer(backdropMaps["topo-world-alt"]),
    };

    worldCalibMap.addLayer(defaultLayer);
    var controlLayers = L.control.layers(baseLayers);
    worldCalibMap.addControl(controlLayers);
    if (L.Browser.touch && L.Browser.mobile) {
      worldCalibMap.on("baselayerchange", function (e) {
        controlLayers.collapse();
      });
    }

    worldCalibMap.on("click", function (e) {
      setRefPtsWorld(e.latlng);
    });

    fetch("https://api.routechoices.com/check-latlon")
      .then(function (r) {
        return r.json();
      })
      .then(function (data) {
        if (data.status === "success") {
          worldCalibMap.setView([data.lat, data.lon], 10, {
            animate: false,
          });
        }
      })
      .catch();
  }

  function round5(x) {
    return Math.round(x * 1e5) / 1e5;
  }

  function buildCalibString(c) {
    var parts = [];
    for (var i = 0; i < c.length; i++) {
      parts.push(round5(c[i].lat) + "," + round5(c[i].lng));
    }
    calibString = parts.join(",");
  }

  function computeCalibString() {
    var xy_a = [];
    var xy_b = [];
    var proj = new SpheroidProjection();
    for (var i = 0; i < markersRaster.length; i++) {
      xy_a[i] = rasterCalibMap.project(markersRaster[i].getLatLng(), 0);
    }
    for (var i = 0; i < markersWorld.length; i++) {
      xy_b[i] = proj.latlng_to_meters(markersWorld[i].getLatLng());
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
    var cornersM = [
      project(matrix3d, 0, 0),
      project(matrix3d, rasterMapImage.width, 0),
      project(matrix3d, rasterMapImage.width, rasterMapImage.height),
      project(matrix3d, 0, rasterMapImage.height),
    ];
    for (var i = 0; i < cornersM.length; i++) {
      cornersLatLng[i] = proj.meters_to_latlng({
        x: cornersM[i][0],
        y: cornersM[i][1],
      });
    }
    buildCalibString(cornersLatLng);
  }

  var iconScale = L.Browser.touch && L.Browser.mobile ? 2 : 1;
  var icons = [
    colorIcon("blue"),
    colorIcon("red"),
    colorIcon("green"),
    colorIcon("orange"),
  ];
  var rasterCalibMap = null;
  var worldCalibMap = null;
  var previewCalibMap = null;
  var previewMap = null;
  var rasterMapImage = null;
  var markersRaster = [];
  var markersWorld = [];
  var cornersLatLng = [];
  var calibString = null;
  var calibHelpTexts = [
    "Select 4 distincts points on the raster map and on the world map.",
    "Check that the raster map is aligned with the world map.",
  ];

  u("#id_image").attr(
    "accept",
    "image/png,image/jpeg,image/gif,image/webp,application/pdf"
  );

  u("#id_image").on("change", function () {
    if (this.files.length > 0 && this.files[0].size > 2 * 1e7) {
      swal({
        title: "Error!",
        text: "File is too big!",
        type: "error",
        confirmButtonText: "OK",
      });
      this.value = "";
    }
    if (this.files.length > 0 && this.value) {
      if (this.files[0].type == "application/pdf") {
        var pdfFile = this.files[0];
        var pdfFileReader = new FileReader();
        pdfFileReader.onload = function (ev) {
          onPDF(ev, pdfFile.name);
        };
        pdfFileReader.readAsArrayBuffer(pdfFile);
        return;
      }
      var bounds = extractCornersCoordsFromFilename(this.files[0].name);
      if (bounds && !u("#id_corners_coordinates").val()) {
        u("#id_corners_coordinates").val(bounds);
      }
      u("#calibration_help").removeClass("d-none");
      u("#id_corners_coordinates").trigger("change");
    } else {
      u("#calibration_help").addClass("d-none");
      u("#calibration_preview").addClass("d-none");
    }
  });

  u("#id_corners_coordinates").on("change", function (e) {
    var val = e.target.value;
    var found = isValidCalibString(val);
    if (found && u("#id_image").val()) {
      u("#calibration_preview").removeClass("d-none");
    } else {
      u("#calibration_preview").addClass("d-none");
    }
  });

  u("#calibration-helper-opener").on("click", function (e) {
    e.preventDefault();
    openCalibrationHelper();
  });

  u("#close-calibration-button").on("click", closeCalibrationHelper);

  u("#reset-raster-markers-button").on("click", function (e) {
    e.preventDefault();
    for (var i = 0; i < markersRaster.length; i++) {
      markersRaster[i].remove();
    }
    markersRaster = [];
    L.DomUtil.addClass(rasterCalibMap._container, "crosshair-cursor");
    u("#to-calibration-step-2-button").addClass("disabled");
  });

  u("#reset-world-markers-button").on("click", function (e) {
    e.preventDefault();
    for (var i = 0; i < markersWorld.length; i++) {
      markersWorld[i].remove();
    }
    markersWorld = [];
    L.DomUtil.addClass(worldCalibMap._container, "crosshair-cursor");
    u("#to-calibration-step-2-button").addClass("disabled");
  });

  u("#to-calibration-step-2-button").on("click", function (e) {
    e.preventDefault();
    computeCalibString();
    u("#calibration-help-text").text(calibHelpTexts[1]);
    u("#calibration-step-1").addClass("d-none");
    u("#calibration-step-2").removeClass("d-none");
    displayCalibPreviewMap();
  });

  u("#back-to-step-1-button").on("click", function (e) {
    e.preventDefault();
    u("#calibration-help-text").text(calibHelpTexts[0]);
    u("#calibration-step-2").addClass("d-none");
    u("#calibration-step-1").removeClass("d-none");
  });

  u("#validate-calibration-button").on("click", function (e) {
    u("#id_corners_coordinates").val(calibString).trigger("change");
    closeCalibrationHelper();
  });

  u("#calibration-preview-opener").on("click", function (e) {
    e.preventDefault();
    u("#main").addClass("d-none");
    u("#calibration-viewer").removeClass("d-none");
    loadCalibString();
    loadMapImagePreview();
  });

  u("#back-from-preview-button").on("click", closePreview);
})();
