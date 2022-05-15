context("Cypress tests", () => {
  beforeEach(() => {
    // https://on.cypress.io/visit
    cy.exec(
      "docker exec rc_django /venv/bin/python3 /app/manage.py reset_db_for_tests"
    );
    cy.getDeviceId();
    cy.visit("/");
  });

  after(() => {
    cy.wait(1000);
  });

  it("Create an Event", function () {
    cy.login();
    cy.url().should("match", /\/dashboard\/select-club$/);

    // Create club
    cy.createClub();

    cy.contains("Halden SK").click();

    // Create Map
    cy.createMap();

    // Create Event with minimal info
    cy.visit("/dashboard/events");
    cy.url().should("match", /\/dashboard\/events$/);
    cy.get("a").contains("Create new event").click();
    cy.url().should("match", /\/dashboard\/events\/new$/);

    cy.get("#id_name").type("Jukola 2019 - 1st Leg");
    cy.get("#id_slug").clear().type("Jukola-2019-1st-leg");
    cy.get("#id_start_date").focus().realType("2019-06-15 20:00:00");
    cy.get("#id_end_date").focus().realType("2019-06-16 10:00:00");
    cy.get("#id_map").select("Jukola 2019 - 1st Leg");

    cy.get("input[value='Save']").click();
    cy.url().should("match", /\/dashboard\/events$/);

    cy.get("a").contains("Jukola 2019 - 1st Leg").click();
    const startListFileName = "startlist.csv";
    cy.get("#csv_input").attachFile(startListFileName);
    cy.get("#id_competitors-2-name").should("have.value", "Frederic Tranchand");
    cy.get("button[name='save_continue']").click();

    cy.get("#upload_route_btn").click();
    cy.get("#id_competitor").select("Daniel Hubman");

    const gpxFileName = "Jukola_1st_leg.gpx";
    cy.get("#id_gpx_file").attachFile(gpxFileName);
    cy.get("input[value='Upload']").click();

    cy.contains("The upload of the GPX file was successful");

    cy.forceVisit("/halden-sk/Jukola-2019-1st-leg");
    cy.contains("Olav Lundanes");
    cy.contains("KooVee");

    // Create Event with all fields info
    cy.visit("/dashboard/events");
    cy.url().should("match", /\/dashboard\/events$/);
    cy.get("a").contains("Create new event").click();
    cy.url().should("match", /\/dashboard\/events\/new$/);

    cy.get("#id_name").type("Jukola 2019 - 1st Leg (2)");
    cy.get("#id_slug").clear().type("Jukola-2019-1st-leg-2");
    cy.get("#id_start_date").focus().realType("2019-06-15 20:00:00");
    cy.get("#id_end_date").focus().realType("2019-06-16 00:00:00");
    cy.get("#id_map").select("Jukola 2019 - 1st Leg");
    cy.get("#id_competitors-0-device-ts-control").type(this.devId).wait(1000);
    cy.get("#id_competitors-0-name").type("Mats Haldin");
    cy.get("#id_competitors-0-short_name").type("Halden");
    cy.get("#id_competitors-0-start_time")
      .focus()
      .realType("2019-06-15 20:00:10");

    cy.intercept("POST", "/dashboard/events/new").as("eventSubmit");
    cy.get("input[value='Save']").click();
    cy.wait("@eventSubmit").then(({ request, response }) => {
      expect(response.statusCode).to.eq(302);
      expect(request.body).to.contain("&competitors-0-device=2&");
    });
    cy.url().should("match", /\/dashboard\/events$/);
    cy.forceVisit("/halden-sk/Jukola-2019-1st-leg-2");

    // trigger as many errors has possible
    cy.visit("/dashboard/events");
    cy.url().should("match", /\/dashboard\/events$/);
    cy.get("a").contains("Create new event").click();
    cy.url().should("match", /\/dashboard\/events\/new$/);

    cy.get("#id_name").type("Jukola 2019 - 1st Leg (2)");
    cy.get("#id_slug").clear().type("Jukola-2019-1st-leg-2");
    cy.get("#id_start_date").focus().realType("2019-06-15 20:00:00");
    cy.get("#id_end_date").focus().realType("2019-06-14 00:00:00");
    cy.get("#id_map_assignations-0-map").select("Jukola 2019 - 1st Leg");
    cy.get("#id_competitors-0-device-ts-control").type(this.devId).wait(1000);
    cy.get("#id_competitors-0-start_time")
      .focus()
      .realType("2019-06-16 20:00:10");
    cy.get("input[value='Save']").click();
    cy.url().should("match", /\/dashboard\/events\/new$/);
    cy.contains("Start Date must be before End Date");
    cy.contains("Event with this Club and Slug already exists.");
    cy.contains("Event with this Club and Name already exists.");
    cy.contains(
      "Extra maps can be set only if the main map field is set first"
    );
    cy.contains("Competitor start time should be during the event time");
  });
});
