(function () {
  var map = null;
  var raster_map_image;
  var corners_latlng = [];
  var calib_string = null;

  function resetOrientation(src, callback) {
    loadImage(
      src,
      function (d) {
        callback(d.toDataURL("image/png"));
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
            raster_map_image = img;
            display_preview_map();
          };
          img.src = imgDataURI;
        });
      };
      fr.readAsDataURL(imageInput.files[0]);
    } else if (imageURL) {
      var img = new Image();
      img.addEventListener("load", function () {
        raster_map_image = img;
        display_preview_map();
      });
      img.src = imageURL;
    } else {
      window.close();
    }
  }

  function isValidCalibString(s) {
    return s.match(/^(\-?\d+\.\d+,){7}\-?\d+\.\d+$/);
  }

  function loadCalibString() {
    var el = window.opener.document.querySelector("#id_corners_coordinates");
    calib_string = el.value;
    if (!calib_string || !isValidCalibString) {
      window.close();
      return;
    }
    var vals = calib_string.split(",").map(function (x) {
      return parseFloat(x);
    });
    corners_latlng = [
      { lat: vals[0], lng: vals[1] },
      { lat: vals[2], lng: vals[3] },
      { lat: vals[4], lng: vals[5] },
      { lat: vals[6], lng: vals[7] },
    ];
  }

  function display_preview_map() {
    map = L.map("preview_map");
    var baseLayers = {};
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
      url: "https://tile.opentopomap.org/{z}/{x}/{y}.png",
      options: { attribution: "&copy; OpenTopoMap (CC-BY-SA)" },
    });
    L.TileLayer["world-topo-alt"] = L.TileLayer.Common.extend({
      url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}",
      options: { attribution: "&copy; Argis Online" },
    });
    L.TileLayer["mapant-no"] = L.TileLayer.Common.extend({
      url: "https://mapant.no/osm-tiles/{z}/{x}/{y}.png",
      options: { attribution: "&copy; MapAnt.no" },
    });
    L.TileLayer["mapant-es"] = L.tileLayer.wms("https://mapant.es/wms", {
      layers: "mapant.es",
      format: "image/png",
      version: "1.3.0",
      transparent: true,
      attribution: "&copy; MapAnt.es",
    });

    var defaultLayer = new L.TileLayer["osm"]();
    baseLayers["Open Street Map"] = defaultLayer;
    baseLayers["Google Map Street"] = new L.TileLayer["gmap-street"]();
    baseLayers["Google Map Satellite"] = new L.TileLayer["gmap-hybrid"]();
    baseLayers["Mapant Finland"] = new L.TileLayer["mapant-fi"]();
    baseLayers["Mapant Norway"] = new L.TileLayer["mapant-no"]();
    baseLayers["Mapant Spain"] = L.TileLayer["mapant-es"];
    baseLayers["Topo Finland"] = new L.TileLayer["finland-topo"]();
    baseLayers["Topo Norway"] = new L.TileLayer["norway-topo"]();
    baseLayers["Topo World (OpenTopo)"] = new L.TileLayer["world-topo"]();
    baseLayers["Topo World (ArcGIS)"] = new L.TileLayer["world-topo-alt"]();

    map.addLayer(defaultLayer);
    var bounds = corners_latlng;

    var transformedImage = L.imageTransform(raster_map_image.src, bounds, {
      opacity: 0.7,
    });
    transformedImage.addTo(map);

    var controlLayers = new L.Control.Layers(baseLayers, {
      Map: transformedImage,
    });
    map.addControl(controlLayers);
    if (L.Browser.touch && L.Browser.mobile) {
      map.on("baselayerchange", function (e) {
        controlLayers.collapse();
      });
    }

    map.fitBounds(bounds);
  }

  u("#back_button").on("click", function (e) {
    e.preventDefault();
    window.close();
  });

  if (!window.opener) {
    window.location.href = "/";
  } else {
    loadCalibString();
    loadMapImage();
  }
})();
