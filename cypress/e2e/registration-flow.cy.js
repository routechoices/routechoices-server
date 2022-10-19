context("Cypress tests", () => {
  beforeEach(() => {
    // https://on.cypress.io/visit
    cy.exec(
      "docker exec rc_django /venv/bin/python3 /app/manage.py reset_db_for_e2e_test --spec=" +
        Cypress.spec.relative
    );
    cy.visit("/");
  });

  after(() => {
    cy.wait(1000);
  });

  it("Register to an Event", function () {
    cy.forceVisit("/halden-sk/Jukola-2040-1st-leg/contribute");
    cy.contains("Add competitor");
    cy.get("#id_name").type("Thierry Gueorgiou");
    cy.get("#id_short_name").type("🇫🇷 T.Gueorgiou");
    cy.get("#id_device_id-ts-control").type("123456").wait(1000).blur();
    cy.get("input[value='Add competitor']").click();
    cy.contains("Competitor Added!");
  });
});
