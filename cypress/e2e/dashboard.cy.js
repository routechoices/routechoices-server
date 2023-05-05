context("Dashboard actions", () => {
  before(() => {
    // https://on.cypress.io/visit
    cy.getDeviceId();
    cy.visit("/");
  });

  after(() => {
    cy.wait(100);
  });

  it("Create an Event", function () {
    cy.login();
    cy.url().should("match", /\/dashboard\/clubs$/);

    // Create club
    cy.createClub();

    cy.contains("Kangasala SK").click();

    // Calibrate a map
    cy.visit("/dashboard/maps/new");

    cy.get("#id_name").type("Jukola 2019 - 1st Leg (manual calibration)");

    cy.get("#id_image").selectFile("cypress/fixtures/Jukola_1st_leg.jpg");

    cy.get("#calibration-preview-opener").should("not.be.visible");
    cy.get("#calibration-helper-opener").click();
    cy.wait(1000);
    cy.get("#to-calibration-step-2-button").should("have.class", "disabled");
    cy.get("#raster-map").click(70, 10);
    cy.get("#world-map").click(70, 10);
    cy.get("#raster-map").click(200, 10);
    cy.get("#world-map").click(200, 10);
    cy.get("#raster-map").click(200, 200);
    cy.get("#world-map").click(200, 200);
    cy.get("#raster-map").click(10, 200);
    cy.get("#world-map").click(10, 200);

    cy.get("#to-calibration-step-2-button").should(
      "not.have.class",
      "disabled"
    );
    cy.get("#to-calibration-step-2-button").click();

    cy.get("#validate-calibration-button").click();

    cy.get("#calibration-preview-opener").should("be.visible");
    cy.get("#id_corners_coordinates")
      .invoke("val")
      .then((val) => {
        expect(/^[-]?\d+(\.\d+)?(,[-]?\d+(\.\d+)?){7}$/.test(val));
      });

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

    cy.get("#submit-btn").click();
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
    cy.get("input[value='Upload']").click();

    cy.contains("The upload of the GPX file was successful");

    cy.forceVisit("/kangasala-sk/Jukola-2019-1st-leg");
    cy.contains("Olav Lundanes", { timeout: 20000 }); // in competitor list
    cy.contains("#map", "KooVee");
    cy.get(".competitor-switch").eq(1).uncheck();
    cy.contains("#map", "KooVee").should("not.exist");

    // Create Event with all fields info
    cy.visit("/dashboard/events");
    cy.url().should("match", /\/dashboard\/events$/);
    cy.get("a").contains("Create new event").click();
    cy.url().should("match", /\/dashboard\/events\/new$/);

    cy.get("#id_name").type("Jukola 2019 - 2nd Leg");
    cy.get("#id_start_date").focus().realType("2019-06-15 20:00:00");
    cy.get("#id_end_date").focus().realType("2019-06-16 00:00:00");
    cy.get("#id_map").select("Jukola 2019 - 1st Leg"); // doesnt matter
    cy.get("#id_competitors-0-device-ts-control").type(this.devId).wait(1000);
    cy.get("#id_competitors-0-name").type("Mats Haldin");
    cy.get("#id_competitors-0-short_name").type("Halden");
    cy.get("#id_competitors-0-start_time")
      .focus()
      .realType("2019-06-15 20:00:10");

    cy.intercept("POST", "/dashboard/events/new").as("eventSubmit");
    cy.get("#submit-btn").click();
    cy.wait("@eventSubmit").then(({ request, response }) => {
      expect(response.statusCode).to.eq(302);
      expect(request.body).to.contain("&competitors-0-device=2&");
    });
    cy.url().should("match", /\/dashboard\/events$/);
    cy.forceVisit("/kangasala-sk/Jukola-2019-2nd-leg");
    cy.contains("Haldin", { timeout: 20000 });
    cy.get(".color-tag").first().click();
    cy.contains("Select new color for Mats");

    // trigger as many errors has possible
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
      .realType("2019-06-16 20:00:10");
    cy.get("#submit-btn").click();
    cy.url().should("match", /\/dashboard\/events\/new$/);
    cy.contains("Start Date must be before End Date");
    cy.contains("Event with this Club, Event Set, and Name already exists.");
    cy.contains("Event with this Club and Slug already exists.");
    cy.contains(
      "Extra maps can be set only if the main map field is set first"
    );
    cy.contains("Competitor start time should be during the event time");
  });
});
