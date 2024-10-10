context("Dashboard actions", () => {
  before(() => {
    // https://on.cypress.io/visit
    cy.getDeviceId();
    cy.visit("/");
  });

  after(() => {
    cy.wait(100);
  });

  it("Manage Participations", function () {
    cy.login();
    cy.forceVisit("/halden-sk/open-registration-upload-allowed/contribute");
    cy.contains("Enter yourself");
    cy.get("#id_name").type("Thierry Gueorgiou");
    cy.get("#id_short_name").type("🇫🇷 T.Gueorgiou");
    cy.get("#id_device_id-ts-control").type("123456").wait(1000).blur();
    cy.get("button:not([type]),button[type=submit]").eq(0).click();
    cy.contains("Competitor added!");
    cy.get(".upload-route-btn").first().click();
    cy.get("#id_gpx_file").selectFile("cypress/fixtures/Jukola_1st_leg.gpx");
    cy.get("#uploadRouteModal button:not([type]),button[type=submit]").click();
    cy.contains("Data uploaded!");

    cy.forceVisit("/dashboard/participations");
    cy.contains(
      "My event with open registration and upload allowed by Halden SK as Thierry Gueorgiou (🇫🇷 T.Gueorgiou)"
    );
    cy.get(".edit-name-btn").first().click();
    cy.get("#id_name").clear().type("Kasper Harlem Fosser");
    cy.get("#id_short_name").clear().type("🇳🇴 K.H.Fosser{enter}");
    cy.contains("Name updated!");
    cy.contains(
      "My event with open registration and upload allowed by Halden SK as Kasper Harlem Fosser (🇳🇴 K.H.Fosser)"
    );

    cy.get(".open-upload-btn").first().click();
    cy.get("#id_gpx_file").selectFile("cypress/fixtures/Jukola_1st_leg.gpx");
    cy.get(".upload-btn:not(.disabled)").click();
    cy.contains("Data uploaded!");
  });

  it("Manage devices", function () {
    cy.login();
    cy.contains("Halden SK").click();
    cy.contains("Devices").click();
    cy.contains("Add new device").click();
    cy.get("#id_device-ts-control").type(this.devId).wait(1000);
    cy.get("#id_nickname").type("MyDevice");
    cy.get("input").contains("Add").click();
    cy.get("#django-messages").contains("Device added successfully");
    cy.contains("MyDevice");
    cy.get(".edit-nick-btn").first().click();
    cy.get("input[placeholder='Nickname'")
      .clear()
      .type("Dev1")
      .wait(500)
      .type("{enter}");
    cy.contains("Dev1");
    cy.contains("MyDevice").should("not.exist");
    cy.get(".remove-btn").first().click().wait(500);
    cy.get("button.confirm").click();
  });

  it("Upgrade Account", function () {
    cy.login();
    cy.contains("Halden SK").click();
    cy.contains("Upgrade to our paid plan!").click();
    cy.url().should("match", /\/upgrade$/);
    cy.contains("Upgrade my subscription").click();
    cy.get("#price-per-month").focus().clear().type("9.99");
    cy.contains("Proceed to payment").click();
    cy.origin("https://store.routechoices.com", () => {
      cy.contains("Test mode is currently enabled.");
    });
  });

  it("Map importers", function () {
    cy.login();
    cy.contains("Halden SK").click();
    ["trk", "waypoint", "waypoint+trk"].forEach((gpxFileName) => {
      cy.visit("/dashboard/maps/upload-gpx");
      cy.get("#id_gpx_file").selectFile(
        "cypress/fixtures/" + gpxFileName + ".gpx"
      );
      cy.get("button:not([type]),button[type=submit]").click();
      cy.get("#django-messages").contains(
        "The import of the map was successful"
      );
    });

    cy.visit("/dashboard/maps/upload-kmz");
    cy.get("#id_file").selectFile("cypress/fixtures/Jukola_1st_leg.kmz");
    cy.get(".sa-confirm-button-container .confirm").click();
    cy.get("button:not([type]),button[type=submit]").click();
    cy.get("#django-messages").contains("The import of the map was successful");
  });

  it("Create Map from Image", function () {
    cy.login();
    cy.contains("Halden SK").click();

    cy.visit("/dashboard/maps/new");

    cy.get("#id_name").type("Jukola 2019 - 1st Leg (manual calibration)");

    cy.get("#id_image").selectFile("cypress/fixtures/Jukola_1st_leg.jpg");

    cy.get("#calibration-preview-opener").should("not.be.visible");
    cy.get("#calibration-helper-opener").click();
    cy.wait(1000);
    cy.get("#raster-map").click(70, 10);
    cy.get("#world-map").click(70, 10);
    cy.get("#raster-map").click(200, 10);
    cy.get("#world-map").click(200, 10);
    cy.get("#raster-map").click(200, 200);
    cy.get("#world-map").click(200, 200);
    cy.get("#raster-map").click(10, 200);
    cy.get("#world-map").click(10, 200);

    cy.get("#to-calibration-step-2-button").click();

    cy.get("#validate-calibration-button").click();

    cy.get("#calibration-preview-opener").should("be.visible");
    cy.get("#id_corners_coordinates")
      .invoke("val")
      .then((val) => {
        expect(/^[-]?\d+(\.\d+)?(,[-]?\d+(\.\d+)?){7}$/.test(val));
      });
    cy.get("button:not([type]),button[type=submit]").click();

    cy.get("#django-messages").contains("Map created successfully");
  });

  it("Create a club", function () {
    cy.login();

    cy.url().should("match", /\/dashboard\/clubs\?next=\/dashboard\/$/);

    // Create club
    cy.createClub();
    cy.contains("Kangasala SK");

    // modify club
    cy.url().should("match", /\/dashboard\/club$/);
    cy.get("#id_website").type("https://www.kangasalask.fi");
    cy.get("#id_description")
      .clear()
      .type("## Kangasala SK  \n## GPS Tracking");

    cy.get("#id_logo").selectFile("cypress/fixtures/KSK_logo.png");
    cy.get("#id_banner").selectFile("cypress/fixtures/KSK_banner.jpg");

    cy.get("button:not([type]),button[type=submit]").click();
    cy.contains("Changes saved successfully", { timeout: 10000 });
  });

  it("Create events", function () {
    cy.login();
    cy.contains("Halden SK").click();

    // Create Map
    cy.createMap();

    // Create Event with minimal info
    cy.visit("/dashboard/events");
    cy.url().should("match", /\/dashboard\/events$/);
    cy.get("a").contains("Create new event").click();
    cy.url().should("match", /\/dashboard\/events\/new$/);

    cy.get("#id_name").type("Jukola 2019 - 1st Leg");
    cy.get("#id_start_date").focus().realType("2019-06-15 20:00:00");
    cy.get("#id_end_date").focus().realType("2019-06-16 10:00:00");
    cy.get("#id_map").select("Jukola 2019 - 1st Leg");

    cy.get("button:not([type]),button[type=submit]").first().click();

    cy.url().should("match", /\/dashboard\/events$/);

    cy.get("a").contains("Jukola 2019 - 1st Leg").click();
    const startListFileName = "startlist.csv";
    cy.get("#csv_input").selectFile("cypress/fixtures/" + startListFileName);
    cy.get("#id_competitors-2-name").should("have.value", "Frederic Tranchand");
    cy.get("button[name='save_continue']").click();

    cy.get("#upload_route_btn").click();
    cy.get("#id_competitor").select("Daniel Hubman");

    const gpxFileName = "Jukola_1st_leg.gpx";
    cy.get("#id_gpx_file").selectFile("cypress/fixtures/" + gpxFileName);
    cy.get("button:not([type]),button[type=submit]").click();

    cy.contains("The upload of the GPX file was successful");

    cy.forceVisit("/halden-sk/Jukola-2019-1st-leg");
    cy.contains("Olav Lundanes", { timeout: 20000 }); // in competitor list

    // toggle competitor
    cy.contains("#map", "KooVee");
    cy.get(".competitor-switch").eq(1).uncheck();
    cy.contains("#map", "KooVee").should("not.exist");

    cy.get(".competitor-switch").eq(1).check();
    cy.contains("#map", "KooVee");

    // random location mass start
    cy.get("#real_time_button").should("have.class", "active");
    cy.get("#map").dblclick(70, 100);
    cy.wait(1000);
    cy.get("#real_time_button").should("not.have.class", "active");

    cy.get("#mass_start_button").click();
    cy.wait(1000);

    // Create Event with all fields info
    cy.visit("/dashboard/events");
    cy.url().should("match", /\/dashboard\/events$/);
    cy.get("a").contains("Create new event").click();
    cy.url().should("match", /\/dashboard\/events\/new$/);

    cy.get("#id_name").type("Jukola 2019 - 2nd Leg");
    cy.get("#id_start_date").focus().realType("2019-06-15 21:00:00");
    cy.get("#id_end_date").focus().realType("2019-06-16 00:00:00");
    cy.get("#id_map").select("Jukola 2019 - 1st Leg"); // doesnt matter
    cy.get("#id_competitors-0-device-ts-control").type(this.devId).wait(1000);
    cy.get("#id_competitors-0-name").type("Mats Haldin");
    cy.get("#id_competitors-0-short_name").type("Halden");
    cy.get("#id_competitors-0-start_time")
      .focus()
      .realType("2019-06-15 21:00:10");

    cy.intercept("POST", "/dashboard/events/new").as("eventSubmit");
    cy.get("button:not([type]),button[type=submit]").first().click();
    cy.wait("@eventSubmit").then(({ request, response }) => {
      expect(response.statusCode).to.eq(302);
      expect(request.body).to.contain("&competitors-0-device=2&");
    });
    cy.url().should("match", /\/dashboard\/events$/);
    cy.forceVisit("/halden-sk/Jukola-2019-2nd-leg");
    cy.contains("Haldin", { timeout: 20000 });
    cy.get(".color-tag").first().click();
    cy.contains("Select new color for Mats");
    cy.get(".IroWheel").first().click(50, 50);
    cy.get("#save-color").click();
    // check event can handle multiple maps
    cy.createMap("Another map");
    cy.visit("/dashboard/events");
    cy.get('table a[href*="dashboard/events/"]')
      .contains("Jukola 2019 - 2nd Leg")
      .click();
    cy.get("#id_map_assignations-0-map").select("Another map");
    cy.get("#id_map_assignations-0-title").type("Alt route");
    cy.intercept("POST", "/dashboard/events/*").as("eventSubmit");
    cy.get("button:not([type]),button[type=submit]").first().click();
    cy.wait("@eventSubmit").then(({ request, response }) => {
      expect(response.statusCode).to.eq(302);
    });
    cy.url().should("match", /\/dashboard\/events$/);
    cy.forceVisit("/halden-sk/Jukola-2019-2nd-leg");

    cy.contains("Alt route", { timeout: 20000 });

    // Trigger as many errors has possible
    cy.visit("/dashboard/events");
    cy.url().should("match", /\/dashboard\/events$/);
    cy.get("a").contains("Create new event").click();
    cy.url().should("match", /\/dashboard\/events\/new$/);

    cy.get("#id_name").type("Jukola 2019 - 2nd Leg");
    cy.get("#id_start_date").focus().realType("2019-06-15 20:00:00");
    cy.get("#id_end_date").focus().realType("2019-06-14 00:00:00");
    cy.get("#id_map_assignations-0-map").select("Jukola 2019 - 1st Leg");
    cy.get("#id_competitors-0-device-ts-control").type(this.devId).wait(1000);
    cy.get("#id_competitors-0-start_time")
      .focus()
      .realType("2019-06-16 21:00:10");
    cy.get("button:not([type]),button[type=submit]").first().click();
    cy.url().should("match", /\/dashboard\/events\/new$/);
    cy.contains("Start Date must be before End Date");
    cy.contains(
      "An Event with this Club, Event Set, and Name already exists."
    ).should("not.exist");
    cy.contains("An Event with this Club and Slug already exists.");
    cy.contains(
      "Extra maps can be set only if the main map field is set first"
    );
    cy.contains("Competitor start time should be during the event time");

    cy.get("#id_map").select("Jukola 2019 - 1st Leg");
    cy.get("#id_map_title").type("Alt route");
    cy.get("#id_map_assignations-0-map").select("Jukola 2019 - 1st Leg");
    cy.get("#id_map_assignations-0-title").type("Alt route");

    cy.get("button:not([type]),button[type=submit]").first().click();
    cy.url().should("match", /\/dashboard\/events\/new$/);

    cy.contains("Map assigned more than once in this event");
    cy.contains("Map title given more than once in this event");
  });
});
