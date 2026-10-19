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
	onRouteLoaded(newRoute, missingTimeInfo);
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
	onRouteLoaded(newRoute, missingTimeInfo);
};

const onTCXLoaded = (e) => {
	const xml = e.target.result;
	try {
		parseTCXString(xml, onTCXParsed);
	} catch (e) {
		swal({
			text: "Error parsing your TCX file!",
			title: "error",
			type: "error",
		});
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
			return;
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
		onRouteLoaded(newRoute, missingTimeInfo);
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
		return;
	}
	const ts = newRoute.map((pt) => Math.round(+pt.time / 1e3)).join(",");
	const lats = newRoute.map((pt) => (+pt.latLon[0]).toFixed(5)).join(",");
	const lons = newRoute.map((pt) => (+pt.latLon[1]).toFixed(5)).join(",");
	route = { timestamps: ts, latitudes: lats, longitudes: lons };
	if (JSON.stringify(route).length > 2 * 1e7) {
		route = {};
		u("#id_gpx_file").val("");
		swal({
			text: "File is too big!",
			title: "error",
			type: "error",
		});
	}
}

let route = {};
let signUpRoute = {};

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
	const queryParams = window.location.search;
	if (
		queryParams.includes("competitor-added=1") ||
		queryParams.includes("route-uploaded=1")
	) {
		window.history.pushState("-", null, window.location.pathname);
	}
	if (u("#registration-form").nodes.length) {
		u("#registration-form").on("submit", (e) => {
			e.preventDefault();
			const submitButton = u("#registration-form").find(
				"button:not([type]),button[type=submit]",
			);
			submitButton.attr("disabled", true);
			submitButton
				.find("i")
				.removeClass("fa-file-signature")
				.addClass("fa-spinner fa-spin");
			const formData = new FormData(e.target);
			const data = {
				event_id: window.local.eventId,
				name: formData.get("name"),
				short_name: formData.get("short_name"),
				route: signUpRoute,
			};
			if (formData.get("tag")) {
				data.tag = formData.get("tag");
			}
			if (formData.get("device_id")) {
				data.device_id = formData.get("device_id");
			}
			reqwest({
				url: "/competitors/",
				method: "post",
				type: "json",
				withCredentials: true,
				crossOrigin: true,
				data: data,
				headers: {
					"X-CSRFToken": window.local.csrfToken,
				},
				success: () => {
					window.localStorage.setItem(
						"userInfoRegistration",
						JSON.stringify({
							name: data.name,
							shortName: data.short_name,
							deviceId: data.device_id,
						}),
					);
					window.location = `${window.location.href}?competitor-added=1`;
					return false;
				},
				error: (err) => {
					submitButton.attr("disabled", false);
					submitButton
						.find("i")
						.removeClass("fa-spinner fa-spin")
						.addClass("fa-file-signature");
					if (err.status === 400) {
						swal({
							text: JSON.parse(err.responseText).join("\n"),
							title: "error",
							type: "error",
						});
					} else {
						swal({
							text: "Something went wrong",
							title: "error",
							type: "error",
						});
					}
				},
			});
		});
		u("#id_race_complete").on("change", (e) => {
			const input = u("#id_gps_file");
			console.log(u("#id_race_complete").nodes[0].checked, input.attr("type"))
			if (u("#id_race_complete").nodes[0].checked) {
				if (input.attr("type") !== "hidden") {
					input.parent().removeClass("d-none");
				}
				input.val(null);
				signUpRoute = null;
			} else {
				if (input.attr("type") !== "hidden") {
					input.parent().addClass("d-none");
				}
			}
		});
		u("#id_race_complete").trigger("change");
		u("#id_gps_file").on("change", function (e) {
			signUpRoute = {};
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
					onload(e);
					const isEmpty = Object.keys(route).length === 0;
					if (!isEmpty) {
						signUpRoute = route;
						const selectEl = document.getElementById("id_device_id");
						const control = selectEl?.tomselect;
						control?.clear();
					}
				};
				fr[readFunction](gpsFile);
			}
		});

		if (window.local.eventEnded) {
			u("#id_device_id").parent().addClass("d-none");
		} else {
			const tsDevId = selectizeDeviceInput("select[name='device_id']");
			const warningHTML = u("<div>")
				.append(u("#warning-if-device-id").html())
				.addClass("d-none");
			u("#id_device_id_helptext").append(warningHTML);
			u("select[name='device_id']").on("change", (e) => {
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
	}

	if (u("#id_gpx_file").nodes.length) {
		u("#id_gpx_file").attr("accept", ".gpx,.tcx,.fit");
		u("#id_gpx_file").on("change", function (e) {
			if (this.files.length > 0) {
				const gpsFile = this.files[0];
				const filename = gpsFile.name;
				const fr = new FileReader();
				if (filename.toLowerCase().endsWith(".tcx")) {
					fr.onload = onTCXLoaded;
				} else if (filename.toLowerCase().endsWith(".fit")) {
					fr.onload = onFitLoaded;
					fr.readAsArrayBuffer(gpsFile);
					return;
				} else {
					fr.onload = onGPXLoaded;
				}
				fr.readAsText(gpsFile);
			}
		});
	}
	u(".date-utc").each((el) => {
		$el = u(el);
		$el.text(dayjs($el.data("date")).local().format("LLLL"));
	});

	if (u("#upload-form").nodes.length) {
		u("#upload-form").on("submit", (e) => {
			e.preventDefault();
			const formData = new FormData(e.target);
			const cmp_aid = formData.get("competitor_aid");
			reqwest({
				url: `/competitors/${cmp_aid}/route`,
				method: "post",
				type: "json",
				withCredentials: true,
				crossOrigin: true,
				data: route,
				headers: {
					"X-CSRFToken": window.local.csrfToken,
				},
				success: () => {
					window.location.href = `${window.location.href}?route-uploaded=1`;
				},
				error: (err) => {
					if (err.status === 400) {
						swal({
							text: JSON.parse(err.responseText).join("\n"),
							title: "error",
							type: "error",
						});
					} else {
						swal({
							text: "Something went wrong",
							title: "error",
							type: "error",
						});
					}
				},
			});
		});
	}

	const uploadModalDiv = document.getElementById("uploadRouteModal");
	if (uploadModalDiv) {
		const uploadModal = new bootstrap.Modal(uploadModalDiv);
		const uploadCompetitorOptions = [
			...document.getElementById("id_competitor_aid").options,
		].map((o) => o.value);
		u(".upload-route-btn").each((el) => {
			if (
				!uploadCompetitorOptions.includes(u(el).attr("data-competitor-aid"))
			) {
				u(el).attr({ disabled: true });
				const wrapper = u(
					'<div class="d-inline-block" tabindex="0" data-bs-toggle="tooltip" data-bs-title="Already assigned a route">',
				);
				u(el).wrap(wrapper);
				new bootstrap.Tooltip(wrapper.nodes[0]);
			} else {
				u(el).on("click", (e) => {
					u("#id_competitor_aid").parent().hide();
					u("#id_competitor_aid").val(u(el).attr("data-competitor-aid"));
					u("#uploader-name").text(u(el).attr("data-competitor-name"));
					uploadModal.show();
				});
			}
		});
	} else {
		u(".upload-route-btn").hide();
	}
})();
