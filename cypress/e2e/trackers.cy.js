context("IMEI device id generation", () => {
  it("Create an Device Id", function () {
    cy.visit("/trackers");
    cy.get("#IMEI").clear().type("0123456789");
    cy.get("button[type='submit']").click();
    cy.contains("Invalid IMEI (must be 15 digits)");
    cy.get("#copyDevIdBtn").should("not.be.visible");

    cy.get("#IMEI").clear().type("012345678901234");
    cy.get("button[type='submit']").click();
    cy.contains("Invalid IMEI (check digit does not match)");
    cy.get("#copyDevIdBtn").should("not.be.visible");

    cy.get("#IMEI").clear().type("012345678901237");
    cy.get("button[type='submit']").click();
    cy.get("#copyDevIdBtn").should("be.visible");

    cy.get("#IMEI").clear().type("0123456789O1234");
    cy.get("button[type='submit']").click();
    cy.contains("Invalid IMEI (must be 15 digits)");
    cy.get("#copyDevIdBtn").should("not.be.visible");
  });
});
