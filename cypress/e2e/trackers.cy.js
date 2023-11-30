context("IMEI device id generation", () => {
  it("Create an Device Id", function () {
    cy.visit("/trackers");
    cy.get("#hardware-tab-btn").click();

    // Invalid too short IMEI
    cy.get("#IMEI").clear().type("0123456789");
    cy.get("button:not([type]),button[type=submit]").click();
    cy.contains("Invalid IMEI (must be 15 digits)");
    cy.get("#copyDevIdBtn").should("not.be.visible");

    // Invalid too long IMEI
    cy.get("#IMEI").clear().type("0123456789012345");
    cy.get("button:not([type]),button[type=submit]").click();
    cy.contains("Invalid IMEI (must be 15 digits)");
    cy.get("#copyDevIdBtn").should("not.be.visible");

    // Invalid: Luhn check
    cy.get("#IMEI").clear().type("012345678901234");
    cy.get("button:not([type]),button[type=submit]").click();
    cy.contains("Invalid IMEI (check digit does not match)");
    cy.get("#copyDevIdBtn").should("not.be.visible");

    // Valid
    cy.get("#IMEI").clear().type("012345678901237");
    cy.get("button:not([type]),button[type=submit]").click();
    cy.get("#copyDevIdBtn").should("be.visible");

    // Invalid: Contains a letter           v this is letter "O"
    cy.get("#IMEI").clear().type("0123456789O1234");
    cy.get("button:not([type]),button[type=submit]").click();
    cy.contains("Invalid IMEI (must be 15 digits)");
    cy.get("#copyDevIdBtn").should("not.be.visible");
  });
});
