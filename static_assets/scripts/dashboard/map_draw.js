(function () {
  var map = L.map("map", { tap: false }).setView([0, 0], 2);
  // geocoder (map search)
  var geocoder = L.Control.geocoder({
    defaultMarkGeocode: false,
  });
  geocoder.on("markgeocode", function (e) {
    map.fitBounds(e.geocode.bbox);
  });
  geocoder.addTo(map);

  // maps layer
  var baseLayers = getBaseLayers();
  var defaultLayer = baseLayers["Open Street Map"];
  map.addLayer(defaultLayer);
  var controlLayers = L.control.layers(baseLayers);
  map.addControl(controlLayers);
  if (L.Browser.touch && L.Browser.mobile) {
    map.on("baselayerchange", function (e) {
      controlLayers.collapse();
    });
  }
  // Draw on map
  var drawnItems = new L.FeatureGroup();
  u("#submit-btn").attr({ disabled: true });
  map.addLayer(drawnItems);
  var drawControl = new L.Control.Draw({
    draw: {
      polyline: {
        metric: true,
        feet: false,
        showLength: false,
        shapeOptions: { color: "#f52fe4" },
      },
      polygon: false,
      rectangle: false,
      circle: false,
      marker: false,
      circlemarker: { color: "#f52fe4", fill: false },
    },
    edit: {
      featureGroup: drawnItems,
    },
  });
  map.addControl(drawControl);

  map.on(L.Draw.Event.CREATED, function (e) {
    drawnItems.addLayer(e.layer);
    u("#submit-btn").attr({ disabled: false });
    setGPX();
  });

  map.on(L.Draw.Event.EDITED, function (e) {
    setGPX();
  });

  map.on(L.Draw.Event.DELETED, function (e) {
    var layers = e.layers;
    layers.eachLayer(function (layer) {
      drawnItems.removeLayer(layer);
    });
    if (drawnItems.getLayers().length === 0) {
      u("#submit-btn").attr({ disabled: true });
    } else {
      setGPX();
    }
  });

  var setGPX = function () {
    var lines = [];
    var wpts = [];
    drawnItems.eachLayer(function (layer) {
      if (layer instanceof L.Polyline) {
        lines.push(layer.getLatLngs());
      } else {
        wpts.push(layer.getLatLng());
      }
    });
    var result =
      '<?xml version="1.0" encoding="UTF-8"?><gpx xmlns="http://www.topografix.com/GPX/1/1" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.topografix.com/GPX/1/1 http://www.topografix.com/GPX/1/1/gpx.xsd" version="1.1" creator="routechoices.com">';
    result += lines.reduce((accum, curr) => {
      let segmentTag = "<trk><trkseg>";
      segmentTag += curr
        .map((point) => `<trkpt lat="${point.lat}" lon="${point.lng}"></trkpt>`)
        .join("");
      segmentTag += "</trkseg></trk>";
      return (accum += segmentTag);
    }, "");
    result += wpts.reduce((accum, point) => {
      var wptTag = `<wpt lat="${point.lat}" lon="${point.lng}"></wpt>`;
      return (accum += wptTag);
    }, "");
    result += "</gpx>";
    var file = new File(
      [result],
      "Drawn map " + dayjs().local().format("YYYY-MM-DD HH:mm:ss") + ".gpx",
      { type: "application/xml", lastModified: new Date().getTime() }
    );
    var container = new DataTransfer();
    container.items.add(file);
    u("#id_gpx_file").first().files = container.files;
  };

  // Center on load
  fetch("https://api.routechoices.com/check-latlon")
    .then(function (r) {
      return r.json();
    })
    .then(function (data) {
      if (data.status === "success") {
        map.setView([data.lat, data.lon], 10, {
          duration: 0,
        });
      }
    })
    .catch();
})();
