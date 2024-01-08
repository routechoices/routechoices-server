pdfjsLib.GlobalWorkerOptions.workerSrc =
  "/static/vendor/pdfjs-3.3.122/pdf.worker.js";

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
            if (container.files[0].size > 2 * 1e7) {
              swal({
                title: "Error!",
                text: "File is too big!",
                type: "error",
                confirmButtonText: "OK",
              });
              u("#id_image").nodes[0].value = "";
              return;
            }
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

const Point = (() => {
  function point(x, y) {
    this.x = x;
    this.y = y;
  }
  return point;
})();

const LatLng = (() => {
  function latlng(lat, lng) {
    this.lat = lat;
    this.lng = lng;
  }
  latlng.prototype.distance = function (latlng) {
    const C = Math.PI / 180,
      dlat = this.lat - latlng.lat,
      dlon = this.lng - latlng.lng,
      a =
        Math.pow(Math.sin((C * dlat) / 2), 2) +
        Math.cos(C * this.lat) *
          Math.cos(C * latlng.lat) *
          Math.pow(Math.sin((C * dlon) / 2), 2);
    return 12756274 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  };
  return latlng;
})();

const SpheroidProjection = (() => {
  const pi = Math.PI,
    float180 = 180.0,
    rad = 6378137,
    originShift = pi * rad,
    piOver180 = pi / float180;

  function S() {}

  S.prototype.latlngToMeters = function (latlng) {
    return new Point(
      latlng.lng * rad * piOver180,
      Math.log(Math.tan(((90 + latlng.lat) * piOver180) / 2)) * rad
    );
  };

  S.prototype.metersToLatLng = function (mxy) {
    return new LatLng(
      (2 * Math.atan(Math.exp(mxy.y / rad)) - pi / 2) / piOver180,
      mxy.x / rad / piOver180
    );
  };

  S.prototype.resolution = function (zoom) {
    return (2 * originShift) / (256 * Math.pow(2, zoom));
  };

  S.prototype.zoomForPixelSize = function (pixelSize) {
    for (let i = 0; i < 30; i++) {
      if (pixelSize > this.resolution(i)) {
        return Math.max(i - 1, 0);
      }
    }
  };

  S.prototype.pixelsToMeters = function (px, py, zoom) {
    const res = this.resolution(zoom),
      mx = px * res - originShift,
      my = py * res - originShift;
    return new Point(mx, my);
  };
  return S;
})();

function adjugateMatrix(m) {
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

function multiplyMatrices(a, b) {
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

function multiplyMatrixByVector(m, v) {
  return [
    m[0] * v[0] + m[1] * v[1] + m[2] * v[2],
    m[3] * v[0] + m[4] * v[1] + m[5] * v[2],
    m[6] * v[0] + m[7] * v[1] + m[8] * v[2],
  ];
}

function basisToPoints(a, b, c, d) {
  var m = [a.x, b.x, c.x, a.y, b.y, c.y, 1, 1, 1];
  var v = multiplyMatrixByVector(adjugateMatrix(m), [d.x, d.y, 1]);
  return multiplyMatrices(m, [v[0], 0, 0, 0, v[1], 0, 0, 0, v[2]]);
}

function general2DProjection(
  pt1RefA,
  pt1RefB,
  pt2RefA,
  pt2RefB,
  pt3RefA,
  pt3RefB,
  pt4RefA,
  pt4RefB
) {
  var refAMatrix = basisToPoints(pt1RefA, pt2RefA, pt3RefA, pt4RefA);
  var refBMatrix = basisToPoints(pt1RefB, pt2RefB, pt3RefB, pt4RefB);
  return multiplyMatrices(refBMatrix, adjugateMatrix(refAMatrix));
}

function project(matrix, x, y) {
  var val = multiplyMatrixByVector(matrix, [x, y, 1]);
  return [val[0] / val[2], val[1] / val[2]];
}

function disableBtnToPreview() {
  u("#to-calibration-step-2-button").addClass("d-none");
  u("#to-calibration-step-2-button-disabled").removeClass("d-none");
}
function enableBtnToPreview() {
  u("#to-calibration-step-2-button").removeClass("d-none");
  u("#to-calibration-step-2-button-disabled").addClass("d-none");
}

(function () {
  function openCalibrationHelper() {
    u("#main").addClass("d-none");
    u("#calibration-helper").removeClass("d-none");
    u("#calibration-helper").nodes[0].scrollIntoView();
    disableBtnToPreview();
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

  function show3pointsWarning() {
    u("#three-points-helper").removeClass("d-none");
  }

  function hide3pointsWarning() {
    u("#three-points-helper").addClass("d-none");
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
    if (
      markersWorld.length >= 3 &&
      markersRaster.length >= 3 &&
      !(markersWorld.length == 4 && markersRaster.length == 4)
    ) {
      show3pointsWarning();
    } else {
      hide3pointsWarning();
    }
    if (markersWorld.length >= 3 && markersRaster.length >= 3) {
      enableBtnToPreview();
    } else {
      disableBtnToPreview();
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

    var baseLayers = getBaseLayers();
    var defaultLayer = baseLayers["Open Street Map"];

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

    var baseLayers = getBaseLayers();
    var defaultLayer = baseLayers["Open Street Map"];

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

    var baseLayers = getBaseLayers();
    var defaultLayer = baseLayers["Open Street Map"];

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

  function solveAffineMatrix(r1, s1, t1, r2, s2, t2, r3, s3, t3) {
    const a =
      ((t2 - t3) * (s1 - s2) - (t1 - t2) * (s2 - s3)) /
      ((r2 - r3) * (s1 - s2) - (r1 - r2) * (s2 - s3));
    const b =
      ((t2 - t3) * (r1 - r2) - (t1 - t2) * (r2 - r3)) /
      ((s2 - s3) * (r1 - r2) - (s1 - s2) * (r2 - r3));
    const c = t1 - r1 * a - s1 * b;
    return [a, b, c];
  }

  function deriveAffineTransform(a, b, c) {
    const e = 1e-15;
    a.xy.x -= e;
    a.xy.y += e;
    b.xy.x += e;
    b.xy.y -= e;
    c.xy.x += e;
    c.xy.y += e;
    x = solveAffineMatrix(
      a.xy.x,
      a.xy.y,
      a.latLonMeters.x,
      b.xy.x,
      b.xy.y,
      b.latLonMeters.x,
      c.xy.x,
      c.xy.y,
      c.latLonMeters.x
    );
    y = solveAffineMatrix(
      a.xy.x,
      a.xy.y,
      a.latLonMeters.y,
      b.xy.x,
      b.xy.y,
      b.latLonMeters.y,
      c.xy.x,
      c.xy.y,
      c.latLonMeters.y
    );
    return x.concat(y);
  }

  function computeCalibString() {
    const rasterXY = [];
    const worldXY = [];
    var proj = new SpheroidProjection();
    if (markersRaster.length === 4 && markersWorld.length === 4) {
      for (var i = 0; i < 4; i++) {
        rasterXY[i] = rasterCalibMap.project(markersRaster[i].getLatLng(), 0);
        worldXY[i] = proj.latlngToMeters(markersWorld[i].getLatLng());
      }
      var matrix3d = general2DProjection(
        rasterXY[0],
        worldXY[0],
        rasterXY[1],
        worldXY[1],
        rasterXY[2],
        worldXY[2],
        rasterXY[3],
        worldXY[3]
      );
      var cornersXY = [
        project(matrix3d, 0, 0),
        project(matrix3d, rasterMapImage.width, 0),
        project(matrix3d, rasterMapImage.width, rasterMapImage.height),
        project(matrix3d, 0, rasterMapImage.height),
      ];
      for (var i = 0; i < cornersXY.length; i++) {
        cornersLatLng[i] = proj.metersToLatLng({
          x: cornersXY[i][0],
          y: cornersXY[i][1],
        });
      }
    } else if (markersRaster.length >= 3 && markersWorld.length >= 3) {
      const calPts = [];
      for (var i = 0; i < 3; i++) {
        rasterXY[i] = rasterCalibMap.project(markersRaster[i].getLatLng(), 0);
        worldXY[i] = proj.latlngToMeters(markersWorld[i].getLatLng());
        calPts.push({
          latLonMeters: worldXY[i],
          xy: rasterXY[i],
        });
      }
      const xyToLatLngMetersCoeffs = deriveAffineTransform(...calPts);
      function mapXYtoLatLng(xy) {
        const x =
          xy.x * xyToLatLngMetersCoeffs[0] +
          xy.y * xyToLatLngMetersCoeffs[1] +
          xyToLatLngMetersCoeffs[2];
        const y =
          xy.x * xyToLatLngMetersCoeffs[3] +
          xy.y * xyToLatLngMetersCoeffs[4] +
          xyToLatLngMetersCoeffs[5];
        return proj.metersToLatLng(new Point(x, y));
      }
      cornersLatLng = [
        mapXYtoLatLng(new Point(0, 0)),
        mapXYtoLatLng(new Point(rasterMapImage.width, 0)),
        mapXYtoLatLng(new Point(rasterMapImage.width, rasterMapImage.height)),
        mapXYtoLatLng(new Point(0, rasterMapImage.height)),
      ];
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
    "Select 4 distinct locations on the raster map and match their locations on the world map. The best is to select four points as much apart from each other as possible.",
    "Check that the raster map is aligned with the world map.",
  ];

  u("#id_image").attr(
    "accept",
    "image/png,image/jpeg,image/gif,image/webp,application/pdf"
  );

  u("#id_image").on("change", function () {
    if (
      this.files.length > 0 &&
      this.files[0].size > 2 * 1e7 &&
      this.files[0].type !== "application/pdf"
    ) {
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
      if (!u("#main-form").hasClass("edit-form")) {
        u("#calibration_help").addClass("d-none");
        u("#calibration_preview").addClass("d-none");
      }
    }
  });

  u("#id_corners_coordinates").on("change", function (e) {
    var val = e.target.value;
    var found = isValidCalibString(val);
    if (
      found &&
      (u("#id_image").val() || u("#main-form").hasClass("edit-form"))
    ) {
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
    disableBtnToPreview();
  });

  u("#reset-world-markers-button").on("click", function (e) {
    e.preventDefault();
    for (var i = 0; i < markersWorld.length; i++) {
      markersWorld[i].remove();
    }
    markersWorld = [];
    L.DomUtil.addClass(worldCalibMap._container, "crosshair-cursor");
    disableBtnToPreview();
  });

  u("#to-calibration-step-2-button").on("click", function (e) {
    e.preventDefault();
    computeCalibString();
    u("#calibration-help-text").text(calibHelpTexts[1]);
    u("#calibration-step-1").addClass("d-none");
    u("#calibration-step-2").removeClass("d-none");
    u("#calibration-helper").nodes[0].scrollIntoView();
    displayCalibPreviewMap();
  });

  u("#back-to-step-1-button").on("click", function (e) {
    e.preventDefault();
    u("#calibration-help-text").text(calibHelpTexts[0]);
    u("#calibration-step-2").addClass("d-none");
    u("#calibration-step-1").removeClass("d-none");
    u("#calibration-helper").nodes[0].scrollIntoView();
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
