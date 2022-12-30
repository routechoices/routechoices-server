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
