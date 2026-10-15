const backdropMaps = {
	osm: L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
		attribution:
			'Map data &copy; <a href="http://openstreetmap.org">OpenStreetMap</a> contributors, <a href="http://creativecommons.org/licenses/by-sa/2.0/">CC-BY-SA</a>, Imagery © <a href="http://mapbox.com">Mapbox</a>',
		className: "wms256",
		referrerPolicy: "origin",
	}),
	/*
	"gmap-street": L.tileLayer("https://mt0.google.com/vt/x={x}&y={y}&z={z}", {
		attribution: "Map data &copy; Google",
		className: "wms256",
	}),
	"gmap-hybrid": L.tileLayer(
		"https://mt0.google.com/vt/lyrs=y&hl=en&x={x}&y={y}&z={z}",
		{
			attribution: "Map data &copy; Google",
			className: "wms256",
		},
	),
	"gmap-terrain": L.tileLayer(
		"https://mt0.google.com/vt/lyrs=p&hl=en&x={x}&y={y}&z={z}",
		{
			attribution: "Map data &copy; Google",
			className: "wms256",
		},
	),
*/
	"topo-fi": L.tileLayer.wms("https://tiles.kartat.kapsi.fi/peruskartta", {
		attribution: "Map data &copy; National Land Survey of Finland",
		className: "wms256",
		layers: "peruskartta",
	}),
	/*
	"mapant-ee": L.tileLayer(
		"https://tiles.routechoices.com/proxy/ee/{z}/{x}/{y}.webp",
		{
			attribution:
				"Map data &copy; mapantee.gokartor.se and Estonian Land Board",
			className: "wms256",
		},
	),
	"mapant-fi": L.tileLayer(
		"https://mapant.trailmap.fi/wmts_EPSG3857.php?z={z}&x={x}&y={y}",
		{
			attribution:
				"Map data &copy; MapAnt.fi and National Land Survey of Finland",
			className: "wms256",
		},
	),
	"topo-no": L.tileLayer(
		"https://cache.kartverket.no/v1/wmts/1.0.0/toporaster/default/webmercator/{z}/{y}/{x}.png",
		{
			attribution: "Map data &copy; kartverket.no",
			className: "wms256",
		},
	),
*/
	"topo-uk": L.tileLayer(
		"https://tiles.routechoices.com/proxy/uk/{z}/{x}/{y}.webp",
		{
			attribution: "Map data &copy; Ordnance Survey",
			className: "wms256",
			minZoom: 7,
			maxNativeZoom: 15,
			bounds: [
				[49.75, -9.01],
				[61.01, 2.01],
			],
		},
	),
	/*
	"mapant-no": L.tileLayer("https://mapant.no/osm-tiles/{z}/{x}/{y}.png", {
		attribution: "Map data &copy; MapAnt.no",
		className: "wms256",
	}),
	"mapant-ch": L.tileLayer(
		"https://tiles.routechoices.com/proxy/ch/{z}/{x}/{y}.webp",
		{
			attribution: "Map data &copy; MapAnt.ch",
			className: "wms256",
		},
	),
	"mapant-fr": L.tileLayer(
		"https://tiles.routechoices.com/proxy/fr/{z}/{x}/{y}.webp",
		{
			attribution: "Map data &copy; MapAnt.fr",
			className: "wms256",
			maxNativeZoom: 17,
		},
	),
	"mapant-se": L.tileLayer(
		"https://tiles.routechoices.com/proxy/se/{z}/{x}/{y}.webp",
		{
			attribution: "Map data &copy; gokartor.se",
			className: "wms256",
		},
	),
*/
	"topo-fr": L.tileLayer(
		"https://data.geopf.fr/private/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=GEOGRAPHICALGRIDSYSTEMS.MAPS.SCAN25TOUR&STYLE=normal&TILEMATRIXSET=PM&FORMAT=image%2Fjpeg&TILEMATRIX={z}&TILECOL={x}&TILEROW={y}&APIKEY=ign_scan_ws",
		{
			attribution:
				'Map data <a href="https://www.ign.fr/" target="_blank">&copy; IGN France</a>',
			className: "wms256",
			maxNativeZoom: 16,
		},
	),
	/*
	"mapant-es": L.tileLayer.wms("https://mapant.es/wms", {
		layers: "mapant.es",
		format: "image/png",
		version: "1.3.0",
		transparent: true,
		attribution: "Map data &copy; MapAnt.es",
		className: "wms256",
	}),
*/
	"topo-world": L.tileLayer("https://tile.opentopomap.org/{z}/{x}/{y}.png", {
		attribution: "Map data &copy; OpenTopoMap (CC-BY-SA)",
		className: "wms256",
	}),
	"topo-world-alt": L.tileLayer(
		"https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}",
		{
			attribution: "Map data &copy; ArcGIS Online",
			className: "wms256",
		},
	),
};

function cloneLayer(layer) {
	function cloneOptions(options) {
		const ret = {};
		for (const i in options) {
			const item = options[i];
			if (item?.clone) {
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
		const layers = [];
		layer.eachLayer((inner) => {
			layers.push(cloneLayer(inner));
		});
		return layers;
	}
	const options = cloneOptions(layer.options);
	// Renderers
	if (layer instanceof L.SVG) {
		return L.svg(options);
	}
	if (layer instanceof L.Canvas) {
		return L.canvas(options);
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
	throw `Unknown layer, cannot clone this layer. Leaflet-version: ${L.version}`;
}

const backgroundMapTitles = {
	osm: "Open Street Map",
	/* "gmap-street": "Google Map Street",
	"gmap-hybrid": "Google Map Satellite",
	"gmap-terrain": "Google Map Terrain",
	"mapant-ee": "Mapant Estonia",
	"mapant-fi": "Mapant Finland",
	"mapant-fr": "Mapant France",
	"mapant-no": "Mapant Norway",
	"mapant-es": "Mapant Spain",
	"mapant-se": "Mapant Sweden",
	"mapant-ch": "Mapant Switzerland", */
	"topo-fi": "Topo Finland",
	"topo-fr": "Topo France",
	"topo-no": "Topo Norway",
	"topo-uk": "Topo UK",
	"topo-world": "OpenTopo",
	"topo-world-alt": "ArcGIS",
};

function getBaseLayers() {
	const entries = {};
	for (const [key, value] of Object.entries(backgroundMapTitles)) {
		entries[value] = cloneLayer(backdropMaps[key]);
	}
	return entries;
}
