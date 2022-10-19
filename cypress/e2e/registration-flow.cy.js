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

  it("Register to an Event", function () {
    cy.login();
    cy.url().should("match", /\/dashboard\/clubs$/);

    // Create club
    cy.createClub();

    cy.contains("Halden SK").click();

    // Create Event with minimal info
    cy.visit("/dashboard/events");
    cy.url().should("match", /\/dashboard\/events$/);
    cy.get("a").contains("Create new event").click();
    cy.url().should("match", /\/dashboard\/events\/new$/);

    cy.get("#id_name").type("Jukola 2040 - 1st Leg");
    cy.get("#id_slug").clear().type("Jukola-2040-1st-leg");
    cy.get("#id_start_date").focus().realType("2040-06-15 20:00:00");
    cy.get("#id_end_date").focus().realType("2040-06-16 10:00:00");
    cy.get("#id_open_registration").check();

    cy.get("input[value='Save']").click();
    cy.url().should("match", /\/dashboard\/events$/);

    cy.forceVisit("/halden-sk/Jukola-2040-1st-leg/contribute");
    cy.contains("Add competitor");
    cy.get("#id_name").type("Thierry Gueorgiou");
    cy.get("#id_short_name").type("🇫🇷 T.Gueorgiou");
    cy.get("#id_device_id-ts-control").type(this.devId).wait(1000).blur();
    cy.get("input[value='Add competitor']").click();
    cy.wait(60000);
    cy.contains("Competitor Added!");
  });
});
