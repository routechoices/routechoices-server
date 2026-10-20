function toISOStringWithTimezone(date) {
	const tzOffset = -date.getTimezoneOffset();
	const diff = tzOffset >= 0 ? "+" : "-";

	const pad = (num) => String(Math.floor(Math.abs(num))).padStart(2, "0");

	// Shift the date by the offset to get local time components via toISOString
	const localISOTime = new Date(date.getTime() + tzOffset * 60 * 1000)
		.toISOString()
		.slice(0, -1); // Remove the trailing 'Z'

	const hours = pad(tzOffset / 60);
	const minutes = pad(tzOffset % 60);

	return `${localISOTime}${diff}${hours}:${minutes}`;
}

context("Dashboard actions", () => {
	after(() => {
		cy.wait(100);
	});

	it("Club page edit", () => {
		cy.login();
		cy.visit("https://dashboard.rtchs.localhost/clubs/kimito-sk");
		cy.contains(".admin-user-div", "test-user");
		cy.get(".admin-user-div").should("have.length", 2);
		cy.get(".remove-admin-btn").eq(1).click();
		cy.contains(
			`You are about to remove user "test-user" from the club's administrator list.`,
		);
		cy.wait(500);
		cy.get("button.confirm").click();
		cy.get(".admin-user-div").should("have.length", 1);
		cy.get(".remove-admin-btn").click();
		cy.contains("You must have at least one administrator listed.");
	});

	it("Contribution page", () => {
		cy.visit(
			"https://dashboard.rtchs.localhost/contribute/kimito-sk/open-registration-upload-allowed/",
		);
		cy.contains("Register");
		cy.get("#id_name").type("Thierry Gueorgiou");
		cy.get("#id_short_name").type("🇫🇷 T.Gueorgiou");
		cy.get("#id_device_id-ts-control").type("123456").wait(1000).blur();
		cy.get("button:not([type]),button[type=submit]").eq(0).click();
		cy.contains("Registration successful!");
		cy.get(".upload-route-btn").first().click();

		cy.get("#id_gpx_file").selectFile({
			contents: "cypress/fixtures/Jukola2019/1/gpx/HaldenSK.gpx",
			fileName: "HaldenSK.gpx",
			mimeType: "text/xml",
		});
		cy.get("#uploadRouteModal button:not([type]),button[type=submit]").click();
		cy.contains("Data uploaded!");
	});

	it("Participation page", () => {
		cy.login();
		cy.visit("https://dashboard.rtchs.localhost/participations");
		cy.contains("My event with open registration and upload allowed");
		cy.contains("Kimito SK");
		cy.contains("Aatos");
		cy.contains("å");
		cy.get(".edit-info-btn").first().click();
		cy.get("#id_name").clear().type("Kasper Harlem Fosser");
		cy.get("#id_short_name").clear().type("🇳🇴 K.H.Fosser{enter}");
		cy.contains("Info updated!");
		cy.contains("My event with open registration and upload allowed");
		cy.contains("Kimito SK");
		cy.contains("Kasper Harlem Fosser");
		cy.contains("🇳🇴 K.H.Fosser");

		cy.get(".open-upload-btn").first().click();
		cy.get("#id_gpx_file").selectFile(
			"cypress/fixtures/Jukola2019/1/gpx/PR.gpx",
		);
		cy.get(".upload-btn:not(.disabled)").click();
		cy.contains("Data uploaded!");
	});

	it("Registration website", () => {
		cy.visit("https://registration.rtchs.localhost");
		cy.contains("My event with open registration and upload allowed");
		cy.contains("My future event with open registration");
		cy.contains("My future event with open registration and upload allowed");
	});

	it("Manage devices", () => {
		cy.login();
		cy.visit("https://dashboard.rtchs.localhost/clubs/");
		cy.contains("Kimito SK").click();
		cy.contains("Trackers").click();
		cy.contains("Add Tracker").click();
		cy.get("#id_device-ts-control").type("10000000").wait(1000);
		cy.get("#id_nickname").type("MyDevice");
		cy.get("button").contains("Add").click();
		cy.get("#django-messages").contains("Tracker added successfully");
		cy.contains("MyDevice");
		cy.contains("Edit").first().click();
		cy.get("#id_nickname").clear().type("Dev1").wait(500).type("{enter}");
		cy.contains("Dev1");
		cy.contains("MyDevice").should("not.exist");

		cy.contains("GPSSeuranta.net Proxy").click();
		const tomorrow = new Date();
		tomorrow.setDate(tomorrow.getDate() + 1);
		const untilDate = toISOStringWithTimezone(tomorrow).slice(0, 10);
		cy.contains(`(Until ${untilDate} `);
		cy.contains("GPSSeuranta.net Proxy").click();
		cy.get("body").should("not.contain", `(Until ${untilDate} `);

		cy.contains("Delete").first().click();
		cy.contains("Delete tracker Dev1?");
		cy.get("#type-confirmation").type("DELETE");
		cy.get("#submit-btn").click();
		cy.contains("Tracker deleted");

		cy.contains("Add Tracker").click();
		cy.get("#csv_input").selectFile(`cypress/fixtures/IMEI.csv`);
		cy.get("button").contains("Import").click();
		cy.contains("4 devices imported");
	});

	it("Upgrade account", () => {
		cy.login();
		cy.visit("https://dashboard.rtchs.localhost/clubs/");
		cy.contains("Kimito SK").click();
		cy.contains("Upgrade to our paid plan!").click();
		cy.location("pathname").should("eq", "/clubs/kimito-sk/upgrade");
		cy.contains("Upgrade my subscription").click();
		cy.contains("Proceed to payment").click({ timeout: 30_000 });
		cy.origin("https://routechoices.lemonsqueezy.com", () => {
			cy.contains("Test mode is currently enabled.", { timeout: 30_000 });
		});
	});

	it("Import map", () => {
		cy.login();
		cy.visit("https://dashboard.rtchs.localhost/clubs/");
		cy.contains("Kimito SK").click();

		for (const gpxFileName of ["trk", "waypoint", "waypoint+trk"]) {
			cy.visit(
				"https://dashboard.rtchs.localhost/clubs/kimito-sk/maps/upload-gpx",
			);
			cy.get("#id_gpx_file").selectFile(
				`cypress/fixtures/gpx/${gpxFileName}.gpx`,
			);
			cy.get("button:not([type]),button[type=submit]").eq(1).click();
			cy.get("#django-messages").contains(
				"The import of the map was successful!",
			);
		}

		for (const kmzFileName of ["Jukola2019/1/map.kmz", "maps/tiled.kmz"]) {
			cy.visit("https://dashboard.rtchs.localhost/clubs/kimito-sk/maps/new");
			cy.get("#id_image").selectFile(`cypress/fixtures/${kmzFileName}`);
			cy.get("#main-form button:not([type]),button[type=submit]").click();
			cy.get("#django-messages", { timeout: 10_000 }).contains(
				"Map successfully imported!",
			);
		}
	});

	it("Create map from image", () => {
		cy.login();
		cy.visit("https://dashboard.rtchs.localhost/clubs/");
		cy.contains("Kimito SK").click();

		cy.visit("https://dashboard.rtchs.localhost/clubs/kimito-sk/maps/new");

		cy.get("#id_image").selectFile("cypress/fixtures/Jukola2019/1/map.jpg");
		cy.get("#id_name")
			.clear()
			.type("Jukola 2019 - 1st Leg (manual calibration)");

		cy.get("#calibration-preview-opener").should("have.class", "disabled");
		cy.get("#calibration-helper-opener").click();
		cy.wait(1000);

		cy.get("#to-calibration-step-2-button-disabled").should("be.visible");
		cy.get("#to-calibration-step-2-button").should("not.be.visible");
		cy.get("#raster-map").click(70, 10);
		cy.get("#world-map").click(70, 10);
		cy.get("#raster-map").click(80, 10);
		cy.get("#world-map").click(80, 10);
		cy.get("#raster-map").click(80, 50);
		cy.get("#to-calibration-step-2-button-disabled").should("be.visible");
		cy.get("#to-calibration-step-2-button").should("not.be.visible");
		cy.get("#world-map").click(80, 50);
		cy.get("#to-calibration-step-2-button-disabled").should("not.be.visible");
		cy.get("#to-calibration-step-2-button").should("be.visible");
		cy.get("#raster-map").click(10, 50);
		cy.get("#world-map").click(10, 50);

		cy.get("#to-calibration-step-2-button").click();

		cy.get("#validate-calibration-button").click();

		cy.get("#calibration-preview-opener").should("not.have.class", "disabled");
		cy.get("#id_calibration_string_raw")
			.invoke("val")
			.then((val) => {
				expect(/^[-]?\d+(\.\d+)?(,[-]?\d+(\.\d+)?){7}$/.test(val));
			});
		cy.get("#main-form button:not([type]),button[type=submit]").click();

		cy.get("#django-messages").contains("Map successfully imported!");
	});

	it("Create a club", () => {
		cy.login();

		// Create club
		cy.createClub();
		cy.contains("Kangasala SK");
		cy.location("pathname").should("eq", "/clubs/kangasala-sk/");

		// modify club
		cy.get("#id_website").type("https://www.kangasalask.fi");
		cy.get("#id_description")
			.clear()
			.type("## Kangasala SK  \n## GPS Tracking");

		cy.get("#id_logo").selectFile("cypress/fixtures/KSK_logo.png");
		cy.get("#id_banner").selectFile("cypress/fixtures/KSK_banner.jpg");

		cy.get("button:not([type]),button[type=submit]").click();
		cy.contains("Changes saved successfully", { timeout: 10_000 });
	});

	it("Create events", () => {
		cy.login();
		cy.visit("https://dashboard.rtchs.localhost/clubs/");
		cy.contains("Kimito SK").click();

		// Create Map
		cy.createMap();

		// Create Event with minimal info
		cy.visit("https://dashboard.rtchs.localhost/clubs/kimito-sk/events/");
		cy.get("a").contains("Setup new Event").click();
		cy.location("pathname").should("eq", "/clubs/kimito-sk/events/new");

		cy.get("#id_name").type("Jukola 2019 - 1st Leg");
		cy.get("#id_event_set-ts-control").parent().click().wait(300);
		cy.get("#id_event_set-ts-control").type("{backspace}Jukola 2019").wait(300);
		cy.get(".ts-dropdown-content > .create").click();
		cy.get("#id_start_date").focus().clear().type("2019-06-15T23:00:00");
		cy.get("#id_end_date").focus().clear().type("2019-06-16T12:00:00");
		cy.get("#id_map").select(1);
		cy.get("button:not([type]),button[type=submit]").eq(1).click();

		// Edit event we just created
		cy.location("pathname").should("eq", "/clubs/kimito-sk/events/");
		cy.contains("Jukola 2019 - 1st Leg").closest("tr").contains("Edit").click();

		cy.get("#csv_input").selectFile("cypress/fixtures/startlist.csv");
		cy.get("#id_competitors-2-name").should("have.value", "Samuel Heinonen");
		cy.get("button[name='save_continue']").click();

		const runners = [
			{
				club: "KooVee",
				name: "Tim Robertson",
			},
			{
				club: "PR",
				name: "Samuel Heinonen",
			},
			{
				club: "HaldenSK",
				name: "Niels Christian Hellerud",
			},
		];
		for (const runner of runners) {
			cy.get("#upload_route_btn").click();
			cy.get("#id_competitor").select(runner.name);
			cy.get("#id_gpx_file").selectFile(
				`cypress/fixtures/Jukola2019/1/gpx/${runner.club}.gpx`,
			);
			cy.get("button:not([type]),button[type=submit]").click();
			cy.contains("The upload of the GPX file was successful!");
		}

		// Create second event with all fields info
		cy.createMap("Another map");
		cy.intercept("POST", "/clubs/kimito-sk/events/new").as("eventSubmit");
		cy.visit("https://dashboard.rtchs.localhost/clubs/kimito-sk/events/new");
		cy.get("#id_name").type("Jukola 2019 - 2nd Leg");
		cy.get("#id_event_set-ts-control").parent().click().wait(300);
		cy.get("#id_event_set-ts-dropdown > .option").eq(1).click().wait(300);
		cy.get("#id_start_date").focus().clear().type("2019-06-16T00:00:00");
		cy.get("#id_end_date").focus().clear().type("2019-06-16T03:00:00");
		cy.get("#id_geojson_layer").selectFile(
			"cypress/fixtures/geojson/valid.geojson",
		);
		cy.get("#id_map").select(3); // doesnt matter
		cy.get("#id_map_assignations-0-map").select("Another map");
		cy.get("#id_map_assignations-0-title").type("Another map");
		cy.get("#id_competitors-0-device-ts-control").type("10000000").wait(500);
		cy.get("#id_competitors-0-device-ts-dropdown > .option")
			.eq(0)
			.click()
			.wait(300);
		cy.get("#id_competitors-0-name").type("Björn Ekeberg");
		cy.get("#id_competitors-0-short_name").type("🇳🇴 IL Tyrving");
		cy.get("#id_competitors-0-start_time")
			.focus()
			.clear()
			.type("2019-06-16T00:00:10");
		cy.get("button:not([type]),button[type=submit]").eq(1).click();

		cy.wait("@eventSubmit").then(({ request, response }) => {
			expect(response.statusCode).to.eq(302);
			expect(request.body).to.contain(
				'form-data; name="competitors-0-device"\r\n\r\n2\r\n',
			);
		});
		cy.location("pathname").should("eq", "/clubs/kimito-sk/events/");

		// test the event view
		cy.visit("https://kimito-sk.rtchs.localhost/Jukola-2019-2nd-leg");
		cy.origin("https://kimito-sk.rtchs.localhost", () => {
			cy.contains("Björn Ekeberg", { timeout: 10_000 });
			cy.contains("Another map", { timeout: 10_000 });
		});
	});

	it("Player UI should work", () => {
		// Test the event view
		// TODO: remove depedency on previous other tests
		cy.visit("https://kimito-sk.rtchs.localhost/Jukola-2019-1st-leg");
		cy.contains("Niels Christian Hellerud", { timeout: 20_000 }); // in competitor list

		// toggle competitor
		cy.get("#toggleAllSwitch").uncheck();

		cy.get(".competitor-switch").eq(2).check();
		cy.contains("#map", "🇫🇮 KooVee");
		cy.get(".competitor-switch").eq(2).uncheck();
		cy.contains("#map", "🇫🇮 KooVee").should("not.exist");
		cy.get(".competitor-switch").eq(1).check();
		cy.get('[aria-label="Center"]').eq(1).click();
		cy.contains("#map", "🇫🇮 Paimion Rasti");

		cy.get("#toggleAllSwitch").check();

		// change runner color
		cy.get(".color-tag").eq(1).click();
		cy.contains("Select new color for Samuel Heinonen");
		cy.get(".IroWheel").first().should("be.visible").click(50, 50);
		cy.get("#save-color").click();

		// center on runner
		cy.get('[aria-label="Center"]').eq(1).click();
		cy.wait(200);

		// move progress bar and focus on runner
		cy.get("#full_progress_bar").click(50, 7);
		cy.get(".competitor-focus-btn").eq(1).click();
		cy.wait(500);

		// toogle full route
		cy.get(".competitor-highlight-btn").eq(1).click();
		cy.get(".competitor-full-route-btn").eq(1).click();
		cy.wait(500);
		cy.get(".competitor-highlight-btn").eq(1).click();
		cy.get(".competitor-full-route-btn").eq(1).click();

		// random location mass start
		//cy.get("#synced-starts-check").should("be.checked").check();
		cy.get("#map").dblclick(70, 90);
		cy.wait(500);
		cy.get("#synced-starts-check").should("be.checked");

		// Show grouping
		cy.get("#options_show_button").click();
		cy.get("#toggleClusterSwitch").click();
		cy.get(".leaflet-control-grouping").first().contains("Group A");
		cy.contains("#map", "Group A");
		cy.contains("#map", "🇫🇮 KooVee").should("not.exist");
		cy.contains("#map", "🇫🇮 Paimion Rasti").should("exist");
		cy.get("#toggleClusterSwitch").click();

		// mass start simulation
		cy.get("#synced-starts-check").should("be.checked").check();
		cy.wait(100);
	});
});
