context("Events in future", () => {
  before(() => {
    cy.visit("/");
  });

  after(() => {
    cy.wait(100);
  });

  it("Future events are not listed", function () {
    cy.forceVisit("https://halden-sk.routechoices.dev/");
    cy.contains("My Future").should("not.exist");
  });

  it("Can not see Event as in future", function () {
    cy.forceVisit("https://halden-sk.routechoices.dev/future-default");
    cy.contains("Event has not yet started.");
    cy.contains("Starting in").should("be.visible");
  });

  it("Can not register or upload to Event as registration not open", function () {
    cy.forceVisit(
      "https://halden-sk.routechoices.dev/future-default/contribute"
    );
    cy.get("#registration-form").should("not.exist");
    cy.get("#upload-form").should("not.exist");
  });

  it("Can not export Event as it is not yet started", function () {
    cy.forceVisit("/halden-sk/future-default/export");
    cy.contains("Export is not available yet...");
  });

  it("Can register to an Event if open registration", function () {
    cy.forceVisit(
      "https://halden-sk.routechoices.dev/future-open-registration/contribute"
    );
    cy.contains("Enter yourself");
    cy.get("#id_name").type("Thierry Gueorgiou");
    cy.get("#id_short_name").type("🇫🇷 T.Gueorgiou");
    cy.get("#id_device_id-ts-control").type("123456").wait(1000).blur();
    cy.get("button:not([type]),button[type=submit]").eq(0).click();
    cy.contains("Competitor added!");
  });

  it("Can not upload to an Event even if upload allowed since it is not yet started", function () {
    cy.forceVisit(
      "https://halden-sk.routechoices.dev/future-upload-allowed/contribute"
    );
    cy.get("#registration-form").should("not.exist");
    cy.get("#upload-form").should("not.exist");
  });

  it("Can only add competitor and not upload route to an Event if everything allowed even since it is not yet started", function () {
    cy.forceVisit(
      "https://halden-sk.routechoices.dev/future-open-registration-upload-allowed/contribute"
    );
    cy.get("#registration-form").should("exist");
    cy.get("#upload-form").should("not.exist");
  });
});
