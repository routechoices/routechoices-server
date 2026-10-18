const seletizeOptions = {
	valueField: "id",
	labelField: "device_id",
	searchField: "device_id",
	create: false,
	createOnBlur: false,
	persist: false,
	plugins: ["preserve_on_blur", "change_listener"],
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
};

const createTagWidget = (i) => {
	new TomSelect(i, {
		persist: false,
		createOnBlur: true,
		create: true,
		delimiter: "\u2063",
	});
};

(() => {
	const userTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
	console.log(`User timezone: ${userTimezone}`);
	const timezoneInput = document.getElementById("id_timezone");
	if (timezoneInput && timezoneInput.value !== userTimezone) {
		timezoneInput.value = userTimezone;
	}
	u(".datetimepicker").each((el) => {
		const val = el.value;
		if (val) {
			const date = new Date(
				`${val.substring(0, 10)}T${val.substring(11, 19)}Z`,
			);
			el.value = date.toLocaleString("sv");
		}
	});

	u(".datetimepicker").each((el) => {
		makeFieldNowable(el);
		makeTimeFieldClearable(el);
		el.autocomplete = "off";
		new tempusDominus.TempusDominus(el);
	});

	u('label[for$="-DELETE"]').parent(".form-group").hide();
	$(".formset_row").formset({
		addText: "",
		deleteText: '<i class="fa-solid fa-trash fa-2x"></i>',
		prefix: "competitors",
	});
	u(".dynamic-form-add").hide();
	// next line must come after formset initialization
	let hasArchivedDevices = false;
	u('select[name$="-device"]').each((el) => {
		if (el.options[el.selectedIndex].text.endsWith("*")) {
			hasArchivedDevices = true;
		}
		new TomSelect(el, seletizeOptions);
	});
	if (hasArchivedDevices) {
		u(".table-bottom").before(
			'<div class="form-text"><span>* Archive of original device</span></div>',
		);
	}

	u(".utc-offset").text(`(Timezone ${userTimezone})`);

	const colorModal = new bootstrap.Modal(
		document.getElementById("color-modal"),
	);

	const createColorWidget = (i) => {
		const originalInput = u(i);
		originalInput.hide();
		let color = originalInput.val();
		const colorSelector = u("<b>")
			.addClass("me-2")
			.css({ color, cursor: "pointer" })
			.html("&#11044;")
			.on("click", (e) => {
				e.preventDefault();

				u("#color-picker").html("");
				new iro.ColorPicker("#color-picker", {
					color,
					width: 150,
					display: "inline-block",
				}).on("color:change", (c) => {
					color = c.hexString;
				});

				function saveColor() {
					colorModal.hide();
					u("#save-color").off("click");
					u("#color-modal").off("keypress");

					originalInput.val(color);
					colorSelector.css({ color });
				}

				u("#save-color").on("click", saveColor);

				u("#color-modal").on("keypress", (e) => {
					e.preventDefault();
					if (e.which === 13) {
						saveColor();
					}
				});

				colorModal.show();
			});
		const clearColor = u("<button>")
			.addClass("btn btn-info btn-sm")
			.attr("type", "button")
			.html("Reset")
			.on("click", (e) => {
				e.preventDefault();
				selectColorWidget.remove();
				originalInput.after(setBtn);
				originalInput.val("");
			});
		const selectColorWidget = u("<div>")
			.addClass("text-nowrap")
			.append(colorSelector)
			.append(clearColor);
		const setBtn = u("<button>")
			.addClass("btn btn-info btn-sm")
			.attr("type", "button")
			.html('<i class="fa-solid fa-palette"></i>')
			.on("click", (e) => {
				e.preventDefault();
				color = `#${(((1 << 24) * Math.random()) | 0).toString(16).padStart(6, "0")}`;
				colorSelector.css({ color });
				setBtn.remove();
				originalInput.after(selectColorWidget);
			});
		if (i.value === "") {
			originalInput.after(setBtn);
		} else {
			originalInput.after(selectColorWidget);
		}
	};

	u(".color-input").each(createColorWidget);
	u(".tag-input").each(createTagWidget);

	u("form").on("submit", (e) => {
		u(".datetimepicker").each((el) => {
			const val = el.value;
			if (val) {
				el.value = dayjs.tz(el.value, userTimezone).toISOString();
			}
		});
		u("#submit-btn").attr({ disabled: true });
		u("button[name='save_continue']").addClass("disabled");
		u(e.submitter)
			.find("i")
			.removeClass("fa-floppy-disk")
			.addClass("fa-spinner fa-spin");
	});

	u(".formset_row").each((el) => {
		const row = u(el);
		const compId = row.attr("data-competitor-id");
		const deviceField = row.find('select[name$="-device"]').first();
		if (deviceField.value) {
			const cropBtn = u(
				'<div class="text-end"><button type="button"class="btn btn-info btn-sm mt-1 text-nowrap"><i class="fa-solid fa-scissors"></i> <span>Crop GPS</span></button></div>',
			);
			cropBtn.on("click", () => {
				const defaultEndDateIso = local.eventEndDate;
				const defaultEndDate = new Date(
					`${defaultEndDateIso.substring(0, 10)}T${defaultEndDateIso.substring(11, 19)}Z`,
				);
				const defaultEndDatePrompt = defaultEndDate.toLocaleString("sv");
				swal(
					{
						title: "Enter end time",
						text: "This will archive the device and crop data until the given end date.",
						type: "input",
						inputValue: defaultEndDatePrompt,
						showCancelButton: true,
					},
					(inputValue) => {
						if (inputValue === false) return false;
						if (inputValue === "") {
							return false;
						}
						const endDate = dayjs.tz(inputValue, userTimezone).toDate();
						reqwest({
							url: `/competitors/${compId}/gpx`,
							method: "get",
							success: (response) => {
								const gpxText = new XMLSerializer().serializeToString(
									response.documentElement,
								);
								const parser = new gpxParser();
								parser.parse(gpxText);
								const newRouteTs = [];
								const newRouteLats = [];
								const newRouteLons = [];
								for (const track of [...parser.tracks, ...parser.routes]) {
									for (const point of track.points) {
										if (point.time < endDate) {
											newRouteTs.push(Math.round(+point.time / 1000));
											newRouteLats.push(point.lat);
											newRouteLons.push(point.lon);
										}
									}
								}
								if (newRouteTs.length === 0) {
									swal({
										text: "Cropped route must contain at least one point!",
										title: "error",
										type: "error",
									});
									return;
								}
								reqwest({
									url: `/competitors/${compId}/route`,
									method: "post",
									type: "json",
									data: {
										latitudes: newRouteLats.join(","),
										longitudes: newRouteLons.join(","),
										timestamps: newRouteTs.join(","),
									},
									withCredentials: true,
									crossOrigin: true,
									headers: {
										"X-CSRFToken": window.local.csrfToken,
									},
									success: () => {
										const urlParams = new URLSearchParams(
											window.location.search,
										);
										urlParams.set("d", +new Date());
										window.location.search = urlParams.toString();
										return;
									},
								});
							},
						});
					},
				);
			});
			u(deviceField.tomselect.wrapper).after(cropBtn);
		}
	});
})();
