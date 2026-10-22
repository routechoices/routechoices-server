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
	let missingTimeInfo = false;
	for (const segment of parsedGpx.segments) {
		for (const pos of segment) {
			if (pos.loc[0]) {
				if (pos.time) {
					newRoute.push({ time: pos.time, latLon: [pos.loc[0], pos.loc[1]] });
				} else {
					missingTimeInfo = true;
				}
			}
		}
	}
	return onRouteLoaded(newRoute, missingTimeInfo);
}

const onTCXLoaded = (e) => {
	const xml = e.target.result;
	try {
		return parseTCXString(xml, onTCXParsed);
	} catch (e) {
		swal({
			text: "Error parsing your TCX file!",
			title: "error",
			type: "error",
		});
		return false;
	}
};

const onFitLoaded = (e) => {
	var fitParser = new Fit.FitParser({
		force: true,
		speedUnit: "km/h",
		lengthUnit: "km",
		temperatureUnit: "celsius",
		elapsedRecordField: "timer_time",
		mode: "list",
	});
	fitParser.parse(e.target.result, (error, data) => {
		if (error) {
			swal({
				text: "Error parsing your FIT file!",
				title: "error",
				type: "error",
			});
			return false;
		}
		const newRoute = [];
		let missingTimeInfo = false;
		for (const rec of data.records) {
			if (rec.position_lat) {
				if (rec.timestamp) {
					newRoute.push({
						time: +rec.timestamp,
						latLon: [rec.position_lat, rec.position_long],
					});
				} else {
					missingTimeInfo = true;
				}
			}
		}
		return onRouteLoaded(newRoute, missingTimeInfo);
	});
};

function onRouteLoaded(newRoute, missingTimeInfo) {
	if (!newRoute?.length) {
		if (missingTimeInfo) {
			swal({
				text: "Missing locations date/time information!",
				title: "error",
				type: "error",
			});
		} else {
			swal({
				text: "No locations found in this file!",
				title: "error",
				type: "error",
			});
		}
		return false;
	}
	const ts = newRoute.map((pt) => Math.round(+pt.time / 1e3)).join(",");
	const latlngs = newRoute
		.map((pt) => `${+pt.latLon[0].toFixed(5)} ${+pt.latLon[1].toFixed(5)}`)
		.join(",");
	let route = { timestamps: ts, latlngs: latlngs };
	if (JSON.stringify(route).length > 2 * 1e7) {
		route = {};
		u("#id_gpx_file").val("");
		swal({
			text: "File is too big!",
			title: "error",
			type: "error",
		});
		return false;
	}
	return route;
}

function getGpxData(node, resultRaw) {
	const result = resultRaw ?? { segments: [] };
	switch (node.nodeName) {
		case "name":
			result.name = node.textContent;
			break;
		case "trkseg": {
			const segment = [];
			result.segments.push(segment);
			for (let i = 0; i < node.childNodes.length; i++) {
				const snode = node.childNodes[i];
				if (snode.nodeName === "trkpt") {
					const trkpt = {
						loc: [
							Number.parseFloat(snode.attributes.lat.value),
							Number.parseFloat(snode.attributes.lon.value),
						],
					};
					for (let j = 0; j < snode.childNodes.length; j++) {
						const ssnode = snode.childNodes[j];
						if (ssnode.nodeName === "time") {
							trkpt.time = new Date(ssnode.childNodes[0].data);
						}
					}
					segment.push(trkpt);
				}
			}
			break;
		}
		default:
			break;
	}
	for (let i = 0; i < node.childNodes.length; i++) {
		getGpxData(node.childNodes[i], result);
	}
	return result;
}

const onTCXParsed = (workout) => {
	const newRoute = [];
	let missingTimeInfo = false;
	for (const lap of workout.laps) {
		for (const pos of lap.track) {
			if (pos.latitude) {
				if (pos.datetime) {
					newRoute.push({
						time: +pos.datetime,
						latLon: [pos.latitude, pos.longitude],
					});
				} else {
					missingTimeInfo = true;
				}
			}
		}
	}
	return onRouteLoaded(newRoute, missingTimeInfo);
};

function parseGpx(xmlstr) {
	if (typeof DOMParser === "undefined") {
		function DOMParser() {}
		DOMParser.prototype.parseFromString = (
			str,
			contentType = "application/xml",
		) => {
			if (typeof XMLHttpRequest !== "undefined") {
				const xmldata = new XMLHttpRequest();
				xmldata.open(
					"GET",
					`data:${contentType};charset=utf-8,${encodeURIComponent(str)}`,
					false,
				);
				if (xmldata.overrideMimeType) {
					xmldata.overrideMimeType(contentType);
				}
				xmldata.send(null);
				return xmldata.responseXML;
			}
		};
	}
	const doc = new DOMParser().parseFromString(xmlstr, "text/xml");
	return getGpxData(doc.documentElement);
}

function selectizeDeviceInput(field) {
	return new TomSelect(field, {
		valueField: "device_id",
		labelField: "device_id",
		searchField: "device_id",
		create: false,
		createOnBlur: false,
		persist: false,
		plugins: ["preserve_on_blur"],
		load: (query, callback) => {
			if (query.length < 4) {
				return callback();
			}
			reqwest({
				url: `${window.local.apiBaseUrl}search/device?q=${encodeURIComponent(query)}`,
				method: "get",
				type: "json",
				withCredentials: true,
				crossOrigin: true,
				success: (res) => {
					callback(res.results);
				},
				error: () => {
					callback();
				},
			});
		},
	});
}

(() => {
	if (u("#registration-form").nodes.length) {
		u("#id_race_complete").on("change", (e) => {
			e.preventDefault();
			const input = u("#id_gps_file");
			if (u("#id_gps_file").attr("type") !== "hidden")
				if (u("#id_race_complete").nodes[0].checked) {
					input.parent().removeClass("d-none");
				} else {
					u("#id_gps_file").parent().addClass("d-none");
					u("#id_gps_file").val(null);
					signUpRoute = null;
				}
		});
		u("#id_race_complete").trigger("change");
		u("#id_gps_file").on("change", function () {
			u("id_js_enabled").val("");
			if (this.files.length > 0) {
				const gpsFile = this.files[0];
				const filename = gpsFile.name;
				const fr = new FileReader();
				let onload = null;
				let readFunction = "readAsText";
				if (filename.toLowerCase().endsWith(".tcx")) {
					onload = onTCXLoaded;
				} else if (filename.toLowerCase().endsWith(".fit")) {
					onload = onFitLoaded;
					readFunction = "readAsArrayBuffer";
				} else {
					onload = onGPXLoaded;
				}
				fr.onload = (e) => {
					const route = onload(e);
					const isEmpty = Object.keys(route).length === 0;
					if (!isEmpty) {
						const jsonBlob = new Blob([JSON.stringify(route)], {
							type: "text/plain;charset=us-ascii",
						});
						const jsonFile = new File([jsonBlob], filename, {
							type: "text/plain",
						});
						const dataTransfer = new DataTransfer();
						dataTransfer.items.add(jsonFile);
						const inputElement = document.getElementById("id_gps_file");
						inputElement.files = dataTransfer.files;
						u("id_js_enabled").val("on");
						// Hide the Tracker ID selector
						const selectEl = document.getElementById("id_device");
						const control = selectEl?.tomselect;
						control?.clear();
					}
				};
				fr[readFunction](gpsFile);
			}
		});
	}
	// Selectize Device selector
	{
		const tsDevId = selectizeDeviceInput("select[name='device']");
		const warningHTML = u("<div>")
			.append(u("#warning-if-device-id").html())
			.addClass("d-none");
		u("#id_device_helptext").append(warningHTML);
		u("select[name='device']").on("change", (e) => {
			if (e.target.value) {
				signUpRoute = null;
				u("#id_gps_file").val(null);
				warningHTML.removeClass("d-none");
			} else {
				warningHTML.addClass("d-none");
			}
		});
		let deviceIdfromHash = false;
		if (window.location.hash) {
			const hash = window.location.hash;
			window.history.pushState("-", null, window.location.pathname);
			const searchParams = new URLSearchParams(hash.slice(1));
			const deviceId = searchParams.get("device_id");
			if (deviceId) {
				deviceIdfromHash = true;
				tsDevId.clear();
				tsDevId.clearOptions();
				tsDevId.addOption({ device_id: deviceId });
				tsDevId.setValue(deviceId);
			}
		}
		const savedRegistrationInfoRaw = window.localStorage.getItem(
			"userInfoRegistration",
		);
		if (savedRegistrationInfoRaw) {
			const savedRegistrationInfo = JSON.parse(savedRegistrationInfoRaw);
			const { name, shortName, deviceId } = savedRegistrationInfo;
			u("#id_name").val(name);
			u("#id_short_name").val(shortName);
			if (deviceId && !deviceIdfromHash) {
				tsDevId.clear();
				tsDevId.clearOptions();
				tsDevId.addOption({ device_id: deviceId });
				tsDevId.setValue(deviceId);
				deviceIdfromHash = true;
			}
		}
	}

	if (u("#id_gpx_file").nodes.length) {
		u("#id_gpx_file").attr("accept", ".gpx,.tcx,.fit");
		u("#id_gpx_file").on("change", function () {
			u("id_js_enabled2").val("");
			if (this.files.length > 0) {
				const gpsFile = this.files[0];
				const filename = gpsFile.name;
				const fr = new FileReader();
				let onload = null;
				let readFunction = "readAsText";
				if (filename.toLowerCase().endsWith(".tcx")) {
					onload = onTCXLoaded;
				} else if (filename.toLowerCase().endsWith(".fit")) {
					onload = onFitLoaded;
					readFunction = "readAsArrayBuffer";
				} else {
					onload = onGPXLoaded;
				}
				fr.onload = (e) => {
					const route = onload(e);
					const isEmpty = Object.keys(route).length === 0;
					if (!isEmpty) {
						const jsonBlob = new Blob([JSON.stringify(route)], {
							type: "text/plain;charset=us-ascii",
						});
						const jsonFile = new File([jsonBlob], filename, {
							type: "text/plain",
						});
						const dataTransfer = new DataTransfer();
						dataTransfer.items.add(jsonFile);
						const inputElement = document.getElementById("id_gpx_file");
						inputElement.files = dataTransfer.files;
						u("id_js_enabled2").val("on");
					}
				};
				fr[readFunction](gpsFile);
			}
		});
	}

	u(".date-utc").each((el) => {
		$el = u(el);
		$el.text(dayjs($el.data("date")).local().format("LLLL"));
	});
})();
