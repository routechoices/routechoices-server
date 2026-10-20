const extractCornersCoordsFromFilename = (filename) => {
	const re = /(_[-]?\d+(\.\d+)?){8}_\.(gif|png|jpg|jpeg|webp)$/;
	const found = filename.match(re);
	if (!found) {
		return false;
	}
	const coords = found[0].split("_");
	coords.pop();
	coords.shift();
	return coords.join(",");
};

const onPDF = (ev, filenameRaw) => {
	pdfjsLib.GlobalWorkerOptions.workerSrc =
		"/static/vendor/pdfjs-5.2.133/pdf.worker.js";
	const loadingTask = pdfjsLib.getDocument({
		data: new Uint8Array(ev.target.result.slice(0)),
	});
	loadingTask.promise.then(async (pdf) => {
		try {
			const geospatialData = await GeoPdfParser.parse(ev.target.result);
			if (geospatialData) {
				u("#id_calibration_string_raw")
					.val(geospatialData.coordinates.flat().join(","))
					.trigger("change");
			}
		} catch (error) {
			console.error("Could not read GeoPDF calibration metadata.", error);
		}
		pdf.getPage(1).then(async (page) => {
			const PRINT_RESOLUTION = 300;
			const PRINT_UNITS = PRINT_RESOLUTION / 72.0;
			const CSS_UNITS = 96.0 / 72.0;
			const viewport = page.getViewport({ scale: 1 });
			const width = `${Math.floor(viewport.width * CSS_UNITS)}px`;
			const height = `${Math.floor(viewport.height * CSS_UNITS)}px`;
			// Prepare canvas using PDF page dimensions
			const canvas = document.createElement("canvas");
			canvas.height = Math.floor(viewport.height * PRINT_UNITS);
			canvas.width = Math.floor(viewport.width * PRINT_UNITS);
			const context = canvas.getContext("2d");
			// Render PDF page into canvas context
			const renderContext = {
				canvasContext: context,
				transform: [PRINT_UNITS, 0, 0, PRINT_UNITS, 0, 0],
				viewport: viewport,
			};
			const renderTask = page.render(renderContext);
			renderTask.promise.then(() => {
				const ext = filenameRaw.split(".").pop();
				const filename = `${filenameRaw.slice(0, filenameRaw.length - ext.length)}jpg`;
				canvas.toBlob(
					(blob) => {
						const file = new File([blob], filename, {
							type: "image/jpeg",
							lastModified: new Date().getTime(),
						});
						const container = new DataTransfer();
						container.items.add(file);
						if (container.files[0].size > 2 * 1e7) {
							const imgSubmitBtn = u("#submit-btn");
							const imgFileField = u("#id_image");
							imgFileField.removeClass("is-valid").addClass("is-invalid");
							imgFileField.parent().find(".valid-feedback").remove();
							imgFileField.parent().find(".invalid-feedback").remove();
							imgFileField.after(
								'<div class="invalid-feedback">File is too big, maximum size: 20MB</div>',
							);
							u("#submit-btn").addClass("disabled");
							return;
						}
						u("#id_image").nodes[0].files = container.files;
						u("#id_image").trigger("change");
						u("#id_image").parent().find(".valid-feedback").remove();
						u("#id_image").parent().find(".invalid-feedback").remove();
						if (u("#id_calibration_string_raw").val()) {
							u("#id_image")
								.removeClass("is-invalid")
								.addClass("is-valid")
								.after(
									'<div class="valid-feedback">File ready to upload!</div>',
								);
							u("#submit-btn").removeClass("disabled");
						} else {
							u("#id_image")
								.addClass("is-invalid")
								.removeClass("is-valid")
								.after(
									'<div class="invalid-feedback">You need to calibrate the image manually</div>',
								);
							u("#submit-btn").addClass("disabled");
						}
					},
					"image/jpeg",
					0.8,
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
		const C = Math.PI / 180;
		const dlat = this.lat - latlng.lat;
		const dlon = this.lng - latlng.lng;
		const a =
			Math.sin((C * dlat) / 2) ** 2 +
			Math.cos(C * this.lat) *
				Math.cos(C * latlng.lat) *
				Math.sin((C * dlon) / 2) ** 2;
		return 12756274 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
	};
	return latlng;
})();

const SpheroidProjection = (() => {
	const pi = Math.PI;
	const float180 = 180.0;
	const rad = 6378137;
	const originShift = pi * rad;
	const piOver180 = pi / float180;

	function S() {}

	S.prototype.latlngToMeters = (latlng) =>
		new Point(
			latlng.lng * rad * piOver180,
			Math.log(Math.tan(((90 + latlng.lat) * piOver180) / 2)) * rad,
		);

	S.prototype.metersToLatLng = (mxy) =>
		new LatLng(
			(2 * Math.atan(Math.exp(mxy.y / rad)) - pi / 2) / piOver180,
			mxy.x / rad / piOver180,
		);

	S.prototype.resolution = (zoom) => (2 * originShift) / (256 * 2 ** zoom);

	S.prototype.zoomForPixelSize = function (pixelSize) {
		for (let i = 0; i < 30; i++) {
			if (pixelSize > this.resolution(i)) {
				return Math.max(i - 1, 0);
			}
		}
	};

	S.prototype.pixelsToMeters = function (px, py, zoom) {
		const res = this.resolution(zoom);
		const mx = px * res - originShift;
		const my = py * res - originShift;
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
	const c = Array(9);
	for (let i = 0; i !== 3; ++i) {
		for (let j = 0; j !== 3; ++j) {
			let cij = 0;
			for (let k = 0; k !== 3; ++k) {
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
	const m = [a.x, b.x, c.x, a.y, b.y, c.y, 1, 1, 1];
	const v = multiplyMatrixByVector(adjugateMatrix(m), [d.x, d.y, 1]);
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
	pt4RefB,
) {
	const refAMatrix = basisToPoints(pt1RefA, pt2RefA, pt3RefA, pt4RefA);
	const refBMatrix = basisToPoints(pt1RefB, pt2RefB, pt3RefB, pt4RefB);
	return multiplyMatrices(refBMatrix, adjugateMatrix(refAMatrix));
}

function project(matrix, x, y) {
	const val = multiplyMatrixByVector(matrix, [x, y, 1]);
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

(() => {
	let isNameEdited = u("#id_name").val() !== "";
	u("#id_name").on("change", function () {
		isNameEdited = this.value !== "";
	});

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

	function closePreview() {
		u("#calibration-viewer").addClass("d-none");
		u("#main").removeClass("d-none");
	}

	function resetImageOrientation(src, callback) {
		loadImage(
			src,
			(d) => {
				callback(d.toDataURL("image/png"));
			},
			{
				orientation: 1,
				maxWidth: 4096,
				maxHeight: 4096,
			},
		);
	}

	function loadMapImagePreview() {
		const imageInput = document.querySelector("#id_image");
		const imageURL = u(imageInput).parent().find("a").attr("href");
		if (imageInput.files?.[0]) {
			const fr = new FileReader();
			fr.onload = (e) => {
				resetImageOrientation(e.target.result, (imgDataURI) => {
					const img = new Image();
					img.onload = () => {
						rasterMapImage = img;
						displayPreviewMap();
					};
					img.src = imgDataURI;
				});
			};
			fr.readAsDataURL(imageInput.files[0]);
		} else if (imageURL) {
			const img = new Image();
			img.addEventListener("load", () => {
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

		const imageInput = document.querySelector("#id_image");
		const imageURL = u(imageInput).parent().find("a").attr("href");
		if (imageInput.files?.[0]) {
			const fr = new FileReader();
			fr.onload = (e) => {
				resetImageOrientation(e.target.result, (imgDataURI) => {
					const img = new Image();
					img.onload = () => {
						displayRasterMap(img);
					};
					img.src = imgDataURI;
				});
			};
			fr.readAsDataURL(imageInput.files[0]);
		} else if (imageURL) {
			const img = new Image();
			img.onload = () => {
				displayRasterMap(img);
			};
			img.src = imageURL;
		} else {
			closeCalibrationHelper();
		}
	}

	function colorIcon(color) {
		return new L.Icon({
			iconUrl: `/static/vendor/leaflet-color-markers-1.0.0/img/marker-icon-2x-${color}.png`,
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
			const marker = L.marker(rasterCalibMap.unproject(xy, 0), {
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
			const marker = L.marker(latlng, {
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
		calibString = u("#id_calibration_string_raw").val();
		if (!calibString || !isValidCalibString(calibString)) {
			closePreview();
		}
		const vals = calibString.split(",").map((x) => Number.parseFloat(x));
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
		const bounds = [
			rasterCalibMap.unproject([0, 0]),
			rasterCalibMap.unproject([image.width, image.height]),
		];
		L.imageOverlay(image.src, bounds).addTo(rasterCalibMap);
		rasterCalibMap.fitBounds(bounds);
		rasterMapImage = image;
		rasterCalibMap.on("click", (e) => {
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

		const baseLayers = getBaseLayers();
		const defaultLayer = baseLayers["Open Street Map"];

		previewMap.addLayer(defaultLayer);
		const bounds = cornersLatLng;

		const transformedImage = L.imageTransform(rasterMapImage.src, bounds, {
			opacity: 0.7,
		});
		transformedImage.addTo(previewMap);

		const controlLayers = L.control.layers(baseLayers, {
			Map: transformedImage,
		});
		previewMap.addControl(controlLayers);
		if (L.Browser.touch && L.Browser.mobile) {
			previewMap.on("baselayerchange", (e) => {
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
		const bounds = cornersLatLng;
		previewCalibMap = L.map("test-map").fitBounds(bounds);
		const transformedImage = L.imageTransform(rasterMapImage.src, bounds, {
			opacity: 0.7,
		});
		transformedImage.addTo(previewCalibMap);

		const baseLayers = getBaseLayers();
		const defaultLayer = baseLayers["Open Street Map"];

		const controlLayersPrev = L.control.layers(baseLayers, {
			Map: transformedImage,
		});
		previewCalibMap.addLayer(defaultLayer);
		previewCalibMap.addControl(controlLayersPrev);
		if (L.Browser.touch && L.Browser.mobile) {
			previewCalibMap.on("baselayerchange", (e) => {
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
			.on("markgeocode", (e) => {
				const bbox = e.geocode.bbox;
				worldCalibMap.fitBounds(bbox);
			})
			.addTo(worldCalibMap);

		const baseLayers = getBaseLayers();
		const defaultLayer = baseLayers["Open Street Map"];

		worldCalibMap.addLayer(defaultLayer);
		const controlLayers = L.control.layers(baseLayers);
		worldCalibMap.addControl(controlLayers);
		if (L.Browser.touch && L.Browser.mobile) {
			worldCalibMap.on("baselayerchange", (e) => {
				controlLayers.collapse();
			});
		}

		worldCalibMap.on("click", (e) => {
			setRefPtsWorld(e.latlng);
		});

		fetch(`${window.local.apiRoot}check-latlon`)
			.then((r) => r.json())
			.then((data) => {
				if (data.status === "success") {
					worldCalibMap.setView([data.lat, data.lon], 10, {
						animate: false,
					});
				}
			})
			.catch();
	}

	function round5(x) {
		return x.toFixed(5);
	}

	function buildCalibString(c) {
		const parts = [];
		for (let i = 0; i < c.length; i++) {
			parts.push(`${round5(c[i].lat)},${round5(c[i].lng)}`);
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
		const x = solveAffineMatrix(
			a.xy.x,
			a.xy.y,
			a.latLonMeters.x,
			b.xy.x,
			b.xy.y,
			b.latLonMeters.x,
			c.xy.x,
			c.xy.y,
			c.latLonMeters.x,
		);
		const y = solveAffineMatrix(
			a.xy.x,
			a.xy.y,
			a.latLonMeters.y,
			b.xy.x,
			b.xy.y,
			b.latLonMeters.y,
			c.xy.x,
			c.xy.y,
			c.latLonMeters.y,
		);
		return x.concat(y);
	}

	function computeCalibString() {
		const rasterXY = [];
		const worldXY = [];
		const proj = new SpheroidProjection();
		if (markersRaster.length === 4 && markersWorld.length === 4) {
			for (let i = 0; i < 4; i++) {
				rasterXY[i] = rasterCalibMap.project(markersRaster[i].getLatLng(), 0);
				worldXY[i] = proj.latlngToMeters(markersWorld[i].getLatLng());
			}
			const matrix3d = general2DProjection(
				rasterXY[0],
				worldXY[0],
				rasterXY[1],
				worldXY[1],
				rasterXY[2],
				worldXY[2],
				rasterXY[3],
				worldXY[3],
			);
			const cornersXY = [
				project(matrix3d, 0, 0),
				project(matrix3d, rasterMapImage.width, 0),
				project(matrix3d, rasterMapImage.width, rasterMapImage.height),
				project(matrix3d, 0, rasterMapImage.height),
			];
			for (let i = 0; i < cornersXY.length; i++) {
				cornersLatLng[i] = proj.metersToLatLng({
					x: cornersXY[i][0],
					y: cornersXY[i][1],
				});
			}
		} else if (markersRaster.length >= 3 && markersWorld.length >= 3) {
			const calPts = [];
			for (let i = 0; i < 3; i++) {
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

	const iconScale = L.Browser.touch && L.Browser.mobile ? 2 : 1;
	const icons = [
		colorIcon("blue"),
		colorIcon("red"),
		colorIcon("green"),
		colorIcon("orange"),
	];
	let rasterCalibMap = null;
	let worldCalibMap = null;
	let previewCalibMap = null;
	let previewMap = null;
	let rasterMapImage = null;
	let markersRaster = [];
	let markersWorld = [];
	let cornersLatLng = [];
	let calibString = null;
	const calibHelpTexts = [
		"Select at least 3 distinct locations on the raster map and match their locations on the World map. 4 points calibration is recommended if your image is perspective distorted.",
	];

	u("#id_calibration_string_raw").closest("div").addClass("d-none");

	const imgSubmitBtn = u("#submit-btn");
	const imgFileField = u("#id_image");
	imgFileField.attr("accept", "image/*,application/pdf,.kmz");
	imgFileField.on("change", async function () {
		u("#id_calibration_string_raw").val("");
		u("#id_name").val("").parent().removeClass("d-none");
		u("#calibration-helper-opener").closest("p").removeClass("d-none");
		if (
			this.files.length > 0 &&
			this.files[0].size > 2 * 1e7 &&
			this.files[0].type !== "application/pdf"
		) {
			imgFileField.removeClass("is-valid").addClass("is-invalid");
			imgFileField.parent().find(".valid-feedback").remove();
			imgFileField.parent().find(".invalid-feedback").remove();
			imgFileField.after(
				'<div class="invalid-feedback">File is too big, maximum size: 20MB</div>',
			);
			imgSubmitBtn.addClass("disabled");
			return;
		}
		imgFileField.removeClass("is-invalid");
		imgFileField.parent().find(".valid-feedback").remove();
		imgFileField.parent().find(".invalid-feedback").remove();
		if (this.files.length > 0 && this.value) {
			if (!isNameEdited) {
				u("#id_name").val(this.files[0].name.replace(/\.[^/.]+$/, ""));
				isNameEdited = true;
			}
			if (this.files[0].type === "application/pdf") {
				const pdfFile = this.files[0];
				const pdfFileReader = new FileReader();
				pdfFileReader.onload = (ev) => {
					onPDF(ev, pdfFile.name);
				};
				pdfFileReader.readAsArrayBuffer(pdfFile);
				return;
			} else if (this.files[0].type.startsWith("image/")) {
				const img = new Image();
				img.onload = function () {
					URL.revokeObjectURL(img.src);
					if (this.width * this.height > 89_478_485) {
						imgFileField.removeClass("is-valid").addClass("is-invalid");
						imgFileField.parent().find(".valid-feedback").remove();
						imgFileField.parent().find(".invalid-feedback").remove();
						imgFileField.after(
							'<div class="invalid-feedback">File is too large, maximum size: 89,478,485 pixels</div>',
						);
						imgSubmitBtn.addClass("disabled");
						return;
					}
				};
				img.src = URL.createObjectURL(this.files[0]);
			} else {
				u("#id_calibration_string_raw").val("0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1");
				u("#id_name").val("-kmz-").parent().addClass("d-none");
				u("#calibration-helper-opener").closest("p").addClass("d-none");
				const keyholeFileField = u("#id_image");
				if (this.files.length > 0 && this.files[0].size > 2 * 1e7) {
					keyholeFileField.removeClass("is-valid").addClass("is-invalid");
					keyholeFileField.parent().find(".valid-feedback").remove();
					keyholeFileField.parent().find(".invalid-feedback").remove();
					keyholeFileField.after(
						'<div class="invalid-feedback">File is too big, maximum size: 20MB</div>',
					);
					imgSubmitBtn.addClass("disabled");
					return;
				}
				if (this.files.length > 0) {
					let kml;
					let zip;
					try {
						zip = await JSZip.loadAsync(this.files[0]);
					} catch {
						kml = await this.files[0].text();
					}
					if (
						!kml &&
						zip &&
						zip.files &&
						Object.keys(zip.files)
							.map((x) => x.toUpperCase())
							.includes("DOC.KML")
					) {
						const kmlDocFilename = Object.keys(zip.files).find(
							(x) => x.toUpperCase() === "DOC.KML",
						);
						kml = await zip.file(kmlDocFilename).async("string");
					}
					if (!kml) {
						keyholeFileField.removeClass("is-valid").addClass("is-invalid");
						keyholeFileField.parent().find(".valid-feedback").remove();
						keyholeFileField.parent().find(".invalid-feedback").remove();
						keyholeFileField.after(
							'<div class="invalid-feedback">Invalid file format!</div>',
						);
						imgSubmitBtn.addClass("disabled");
						return;
					}
					let parsedText;
					try {
						const parser = new DOMParser();
						parsedText = parser.parseFromString(kml, "text/xml");
						const errorNode = parsedText.querySelector("parsererror");
						if (errorNode) {
							console.log(errorNode);
							throw Error(errorNode);
						}
					} catch {
						keyholeFileField.removeClass("is-valid").addClass("is-invalid");
						keyholeFileField.parent().find(".valid-feedback").remove();
						keyholeFileField.parent().find(".invalid-feedback").remove();
						keyholeFileField.after(
							'<div class="invalid-feedback">Invalid file format!</div>',
						);
						imgSubmitBtn.addClass("disabled");
						return;
					}
					const nLayers =
						parsedText.getElementsByTagName("GroundOverlay").length;
					if (nLayers === 0) {
						keyholeFileField.removeClass("is-valid").addClass("is-invalid");
						keyholeFileField.parent().find(".valid-feedback").remove();
						keyholeFileField.parent().find(".invalid-feedback").remove();
						keyholeFileField.after(
							'<div class="invalid-feedback">Invalid file format!</div>',
						);
						imgSubmitBtn.addClass("disabled");
						return;
					}
					keyholeFileField.addClass("is-valid").removeClass("is-invalid");
					keyholeFileField.parent().find(".valid-feedback").remove();
					keyholeFileField.parent().find(".invalid-feedback").remove();
					keyholeFileField.after(
						'<div class="valid-feedback">File ready to upload!</div>',
					);
					u("#submit-btn").removeClass("disabled");
				}
			}
			const bounds = extractCornersCoordsFromFilename(this.files[0].name);
			if (bounds && !u("#id_calibration_string_raw").val()) {
				u("#id_calibration_string_raw").val(bounds);
				u("#id_name").val(this.files[0].name.split("_").slice(0, -9).join("_"));
			}
			u("#calibration_help button").removeClass("disabled");
			u("#id_calibration_string_raw").trigger("change");
		} else {
			if (!u("#main-form").hasClass("edit-form")) {
				u("#calibration_help button").addClass("disabled");
				u("#calibration_preview button").addClass("disabled");
				imgSubmitBtn.addClass("disabled");
			}
		}
		if (u("#id_image").val()) {
			u("#id_image").parent().find(".valid-feedback").remove();
			u("#id_image").parent().find(".invalid-feedback").remove();
			if (u("#id_calibration_string_raw").val()) {
				u("#id_image")
					.removeClass("is-invalid")
					.addClass("is-valid")
					.after('<div class="valid-feedback">File ready to upload!</div>');
				u("#submit-btn").removeClass("disabled");
			} else {
				u("#id_image")
					.addClass("is-invalid")
					.removeClass("is-valid")
					.after(
						'<div class="invalid-feedback">You need to calibrate the image manually</div>',
					);
				u("#submit-btn").addClass("disabled");
			}
		}
	});

	u("#id_calibration_string_raw").on("change", (e) => {
		const val = e.target.value;
		const found = isValidCalibString(val);
		u("#id_image").parent().find(".valid-feedback").remove();
		u("#id_image").parent().find(".invalid-feedback").remove();
		if (
			found &&
			(u("#id_image").val() || u("#main-form").hasClass("edit-form"))
		) {
			u("#calibration_preview button").removeClass("disabled");
			u("#submit-btn").removeClass("disabled");
			u("#id_image")
				.removeClass("is-invalid")
				.addClass("is-valid")
				.after('<div class="valid-feedback">File ready to upload!</div>');
			u("#submit-btn").removeClass("disabled");
		} else {
			u("#calibration_preview button").addClass("disabled");
			u("#id_image")
				.addClass("is-invalid")
				.removeClass("is-valid")
				.after(
					'<div class="invalid-feedback">You need to calibrate the image manually</div>',
				);
			u("#submit-btn").addClass("disabled");
		}
	});

	u("#id_image").trigger("change");

	u("#calibration-helper-opener").on("click", (e) => {
		e.preventDefault();
		openCalibrationHelper();
	});

	u("#close-calibration-button").on("click", closeCalibrationHelper);

	u("#reset-raster-markers-button").on("click", (e) => {
		e.preventDefault();
		for (let i = 0; i < markersRaster.length; i++) {
			markersRaster[i].remove();
		}
		markersRaster = [];
		L.DomUtil.addClass(rasterCalibMap._container, "crosshair-cursor");
		disableBtnToPreview();
	});

	u("#reset-world-markers-button").on("click", (e) => {
		e.preventDefault();
		for (let i = 0; i < markersWorld.length; i++) {
			markersWorld[i].remove();
		}
		markersWorld = [];
		L.DomUtil.addClass(worldCalibMap._container, "crosshair-cursor");
		disableBtnToPreview();
	});

	u("#to-calibration-step-2-button").on("click", (e) => {
		e.preventDefault();
		computeCalibString();
		u("#calibration-help-text").text(calibHelpTexts[1]);
		u("#calibration-step-1").addClass("d-none");
		u("#calibration-step-2").removeClass("d-none");
		u("#calibration-helper").nodes[0].scrollIntoView();
		displayCalibPreviewMap();
	});

	u("#back-to-step-1-button").on("click", (e) => {
		e.preventDefault();
		u("#calibration-help-text").text(calibHelpTexts[0]);
		u("#calibration-step-2").addClass("d-none");
		u("#calibration-step-1").removeClass("d-none");
		u("#calibration-helper").nodes[0].scrollIntoView();
	});

	u("#validate-calibration-button").on("click", (e) => {
		u("#id_calibration_string_raw").val(calibString).trigger("change");
		closeCalibrationHelper();
	});

	u("#calibration-preview-opener").on("click", (e) => {
		e.preventDefault();
		u("#main").addClass("d-none");
		u("#calibration-viewer").removeClass("d-none");
		loadCalibString();
		loadMapImagePreview();
	});

	u("#back-from-preview-button").on("click", closePreview);
})();
