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
  // GPS location
  L.control.locate().addTo(map);

  // Draw on map
  var drawnItems = new L.FeatureGroup();
  map.addLayer(drawnItems);
  var drawControl = new L.Control.Draw({
    draw: {
      polyline: {
        metric: true,
        feet: false,
        showLength: true,
      },
      polygon: false,
      rectangle: false,
      circle: false,
      marker: false,
      circlemarker: false,
    },
    edit: {
      featureGroup: drawnItems,
    },
  });
  map.addControl(drawControl);
  function getDistance(polyline) {
    // Calculating the distance of the polyline
    var tempLatLng = null;
    var totalDistance = 0.0;
    if (!polyline?.getLatLngs) return 0;
    polyline?.getLatLngs().forEach(function (latlng, i) {
      if (tempLatLng == null) {
        tempLatLng = latlng;
        return;
      }
      totalDistance += tempLatLng.distanceTo(latlng);
      tempLatLng = latlng;
    });
    return totalDistance;
  }
  map.on(L.Draw.Event.CREATED, function (e) {
    drawnItems.clearLayers();
    drawnItems.addLayer(e.layer);
    if (e.layerType == "polyline") {
      e.layer.bindPopup(getDistance(e.layer).toFixed(2) + " meters");
      e.layer.openPopup();
    }
  });
  map.on("draw:edited", function (e) {
    e.layers.eachLayer(function (layer) {
      layer.bindPopup(getDistance(layer).toFixed(2) + " meters");
      layer.openPopup();
    });
  });

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

  // KMZ uploader
  L.Control.KMZUploader = L.Control.extend({
    onAdd: function (map) {
      var back = L.DomUtil.create(
        "div",
        "leaflet-control leaflet-bar leaflet-kmzuploader"
      );
      back.innerHTML =
        "KMZ:<br/><input id='kmz-uploader' type='file' accept='.kmz' multiple/><br/>GPX:<br/><input id='gpx-uploader' type='file' accept='.gpx' multiple/>";
      L.DomEvent.on(back, "mousewheel", L.DomEvent.stopPropagation);
      L.DomEvent.on(back, "touchstart", L.DomEvent.stopPropagation);
      return back;
    },

    onRemove: function (map) {
      u(".leaflet-control").remove();
    },
  });
  L.control.kmzUploader = function (opts) {
    return new L.Control.KMZUploader(opts);
  };
  kmzControl = L.control.kmzUploader({ position: "bottomright" });
  map.addControl(kmzControl);
  document
    .getElementById("kmz-uploader")
    .addEventListener("change", async function () {
      for (var file of this.files) {
        await onKmzLoaded(file);
      }
    });

  document
    .getElementById("gpx-uploader")
    .addEventListener("change", async function () {
      for (var file of this.files) {
        const reader = new FileReader();
        reader.addEventListener("load", (event) => {
          var parser = new gpxParser();
          parser.parse(event.target.result);
          for (var track of parser.tracks) {
            var latlons = [];
            for (var pt of track.points) {
              latlons.push([pt.lat, pt.lon]);
            }
            var p = L.polyline(latlons);
            console.log(latlons);
            p.addTo(map);
          }
        });
        reader.readAsText(file);
      }
    });
  const extractKMZInfo = async (kmlText, kmz) => {
    const parser = new DOMParser();
    const parsedText = parser.parseFromString(kmlText, "text/xml");
    const go = parsedText.getElementsByTagName("GroundOverlay")[0];
    if (go) {
      try {
        const latLonboxElNodes = go.getElementsByTagName("LatLonBox");
        const latLonQuadElNodes = go.getElementsByTagName("gx:LatLonQuad");
        const filePath = go.getElementsByTagName("href")[0].innerHTML;
        const fileU8 = await kmz.file(filePath).async("uint8array");
        const filename = kmz.file(filePath).name;
        const extension = filename.toLowerCase().split(".").pop();
        let mime = "";
        if (extension === "jpg") {
          mime = "image/jpeg";
        } else if (["png", "gif", "jpeg", "webp", "avif"].includes(extension)) {
          mime = "image/" + extension;
        }
        const imageDataURI =
          "data:" +
          mime +
          ";base64," +
          btoa(
            [].reduce.call(
              fileU8,
              function (p, c) {
                return p + String.fromCharCode(c);
              },
              ""
            )
          );
        let bounds;
        var maps = [];
        for (var i = 0; i < latLonboxElNodes.length; i++) {
          const latLonboxEl = latLonboxElNodes[i];
          bounds = computeBoundsFromLatLonBox(
            parseFloat(latLonboxEl.getElementsByTagName("north")[0].innerHTML),
            parseFloat(latLonboxEl.getElementsByTagName("east")[0].innerHTML),
            parseFloat(latLonboxEl.getElementsByTagName("south")[0].innerHTML),
            parseFloat(latLonboxEl.getElementsByTagName("west")[0].innerHTML),
            parseFloat(
              latLonboxEl.getElementsByTagName("rotation")[0]
                ? latLonboxEl.getElementsByTagName("rotation")[0].innerHTML
                : 0
            )
          );
          maps.push({ imageDataURI, bounds });
        }
        for (var i = 0; i < latLonQuadElNodes.length; i++) {
          const latLonQuadEl = latLonQuadElNodes[i];
          let [sw, se, ne, nw] = latLonQuadEl
            .getElementsByTagName("coordinates")[0]
            .innerHTML.trim()
            .split(" ");
          nw = nw.split(",");
          ne = ne.split(",");
          se = se.split(",");
          sw = sw.split(",");
          bounds = [
            [parseFloat(nw[1]), parseFloat(nw[0])],
            [parseFloat(ne[1]), parseFloat(ne[0])],
            [parseFloat(se[1]), parseFloat(se[0])],
            [parseFloat(sw[1]), parseFloat(sw[0])],
          ];
          maps.push({ imageDataURI, bounds });
        }
        return maps;
      } catch (e) {
        console.log(e);
        alert("Error parsing your KMZ file!");
        return;
      }
    } else {
      console.log(e);
      alert("Error parsing your KMZ file!");
      return;
    }
  };
  const onKmzLoaded = async (file) => {
    const zip = await JSZip.loadAsync(file);
    if (zip.files && zip.files["doc.kml"]) {
      const kml = await zip.file("doc.kml").async("string");
      const maps = await extractKMZInfo(kml, zip);
      if (maps) {
        for (var data of maps) {
          var rmap = L.imageTransform(data.imageDataURI, data.bounds);
          map.addLayer(rmap);
        }
      }
    } else {
      alert("Error parsing your KMZ file!");
    }
  };
})();
