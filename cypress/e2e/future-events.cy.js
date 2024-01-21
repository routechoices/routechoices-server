context("Events in future", () => {
  it("Future events are not listed", function () {
    cy.forceVisit("/halden-sk/");
    cy.contains("My Future").should("not.exist");
  });

  it("Can not see Event as in future", function () {
    cy.forceVisit("/halden-sk/future-default");
    cy.contains("Event not yet started.");
    cy.contains("Starting in");
  });

  it("Can not register or upload to Event as registration not open", function () {
    cy.forceVisit("/halden-sk/future-default/contribute");
    cy.contains("Registration and route upload closed.");
  });

  it("Can not export Event as not yet started", function () {
    cy.forceVisit("/halden-sk/future-default/export");
    cy.contains("Export is not available yet...");
  });

  it("Can register to an Event if open registration", function () {
    cy.forceVisit("/halden-sk/future-open-registration/contribute");
    cy.contains("Add competitor");
    cy.get("#id_name").type("Thierry Gueorgiou");
    cy.get("#id_short_name").type("🇫🇷 T.Gueorgiou");
    cy.get("#id_device_id-ts-control").type("123456").wait(1000).blur();
    cy.get("input[value='Add competitor']").click();
    cy.contains("Competitor Added!");
  });

  it("Can not upload to an Event even if upload allowed since not yet started", function () {
    cy.forceVisit("/halden-sk/future-upload-allowed/contribute");
    cy.contains("Registration and route upload closed.");
  });

  it("Can only add competitor and not upload route to an Event if everything allowed even since not yet started", function () {
    cy.forceVisit(
      "/halden-sk/future-open-registration-upload-allowed/contribute"
    );
    cy.get("#registration-form").should("exist");
    cy.get("#upload-form").should("not.exist");
  });
});
