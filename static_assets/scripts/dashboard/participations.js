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
		return;
	}
	u(".upload-btn").removeClass("disabled");
}

let route = {};

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

(() => {
	let tsDevId = null;
	function selectizeDeviceInput() {
		tsDevId = new TomSelect("select[name='device_id']", {
			valueField: "device_id",
			labelField: "device_id",
			searchField: "device_id",
			create: false,
			createOnBlur: false,
			persist: false,
			plugins: ["preserve_on_blur"],
			allowEmptyOption: true,
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

	selectizeDeviceInput();
	u("#id_device_id").attr("required", true);

	const thisUrl = window.location.href;
	if (
		thisUrl.includes("info-edited=1") ||
		thisUrl.includes("route-uploaded=1") ||
		thisUrl.includes("withdrawn=1")
	) {
		window.history.pushState("-", null, window.location.pathname);
	}

	const editModal = new bootstrap.Modal(
		document.getElementById("editNameModal"),
	);
	const uploadModal = new bootstrap.Modal(
		document.getElementById("uploadRouteModal"),
	);
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

	u(".edit-info-btn").on("click", (e) => {
		const el = u(e.target).closest("button");
		u("#id_name").val(el.attr("data-competitor-name"));
		u("#id_short_name").val(el.attr("data-competitor-short-name"));
		u("#id_id").val(el.attr("data-competitor-id"));
		const currentTag = (el.attr("data-competitor-tags") ?? "").split(" ")?.[0];
		u("#id_tag").text("");
		const allowedTags = (el.attr("data-competition-allowed-tags") ?? "").split(
			"\u2063",
		);
		if ((el.attr("data-competition-allowed-tags") ?? "") !== "") {
			u("#id_tag").append(u("<option>").attr({ value: "" }).text("------"));
			const options = allowedTags.map((t) =>
				u("<option>")
					.attr({ selected: currentTag === t, value: t })
					.text(t),
			);
			for (const option of options) {
				u("#id_tag").append(option);
			}
			u("#id_tag").parent().show();
		} else {
			u("#id_tag").parent().hide();
		}

		tsDevId.clear();
		tsDevId.clearOptions();
		tsDevId.addOption({ device_id: el.attr("data-device-id") });
		tsDevId.setValue(el.attr("data-device-id"));
		editModal.show();
	});

	u(".open-upload-btn").on("click", (e) => {
		const el = u(e.target).closest(".open-upload-btn");
		u("#id_competitor_aid").val(el.attr("data-competitor-id"));
		u("#id_gpx_file").val("");
		uploadModal.show();
	});

	u("#info-form").on("submit", (e) => {
		e.preventDefault();
		const name = u("#id_name").val();
		const shortName = u("#id_short_name").val();
		const competitorId = u("#id_id").val();
		const deviceId = u("#id_device_id").val();
		const tag = u("#id_tag").val();
		const data = {
			name,
			short_name: shortName,
			device_id: deviceId,
		};
		if (u("#id_tag > option").nodes.length > 0) {
			data.tags = tag;
		}
		if (deviceId === "GPS File") {
			delete data.device_id;
		}
		reqwest({
			url: `/competitors/${competitorId}/`,
			method: "PATCH",
			withCredentials: true,
			crossOrigin: true,
			headers: {
				"X-CSRFToken": window.local.csrfToken,
			},
			data,
			success: () => {
				window.location.href = `${window.location.href}?info-edited=1`;
			},
			error: (e) => {
				swal({
					text: "Something went wrong",
					title: "error",
					type: "error",
				});
			},
		});
	});

	u(".confirm-withdraw-btn").on("click", (e) => {
		const el = u(e.target).closest("button");
		const competitorId = el.attr("data-competitor-id");
		const eventName = el.attr("data-event-name");
		swal(
			{
				title: "Confirm withdrawal",
				text: `Are you sure you want to remove yourself from the event "${eventName}"?\nType WITHDRAW to confirm:`,
				type: "input",
				closeOnConfirm: false,
				showCancelButton: true,
				confirmButtonText: "Withdraw",
				confirmButtonClass: "btn-danger withdraw-btn disabled",
			},
			(inputValue) => {
				if (inputValue !== "WITHDRAW") {
					return false;
				}
				reqwest({
					url: `/competitors/${competitorId}/`,
					method: "DELETE",
					withCredentials: true,
					crossOrigin: true,
					headers: {
						"X-CSRFToken": window.local.csrfToken,
					},
					success: () => {
						window.location.href = `${window.location.href}?withdrawn=1`;
					},
					error: (e) => {
						swal({
							text: "Something went wrong",
							title: "error",
							type: "error",
						});
					},
				});
			},
		);
		u(".sweet-alert input").on("keyup", (e) => {
			const el = u(e.target);
			if (el.val() !== "WITHDRAW") {
				u(".withdraw-btn").addClass("disabled").attr("disabled=1");
			} else {
				u(".withdraw-btn").removeClass("disabled").attr("disabled=false");
			}
		});
		u(".sweet-alert input").addClass("mb-2");
	});
	u("#upload-form").on("submit", (e) => {
		e.preventDefault();
		u(".upload-btn").addClass("disabled");
		const competitorId = u("#id_competitor_aid").val();
		reqwest({
			url: `/competitors/${competitorId}/route`,
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
})();
