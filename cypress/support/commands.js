// ***********************************************
// This example commands.js shows you how to
// create various custom commands and overwrite
// existing commands.
//
// For more comprehensive examples of custom
// commands please read more here:
// https://on.cypress.io/custom-commands
// ***********************************************
//
//
// -- This is a parent command --
// Cypress.Commands.add("login", (email, password) => { ... })
//
//
// -- This is a child command --
// Cypress.Commands.add("drag", { prevSubject: 'element'}, (subject, options) => { ... })
//
//
// -- This is a dual command --
// Cypress.Commands.add("dismiss", { prevSubject: 'optional'}, (subject, options) => { ... })
//
//
// -- This is will overwrite an existing command --
// Cypress.Commands.overwrite("visit", (originalFn, url, options) => { ... })
import "cypress-real-events/support";

Cypress.Commands.add(
  "login",
  (username = "admin", password = "pa$$word123") => {
    cy.visit("/login/");
    cy.get("#id_login").type(username);
    cy.get("#id_password").type(password + "{enter}");
  }
);

Cypress.Commands.add("createClub", (name = "Kangasala SK") => {
  cy.visit("/dashboard/clubs/new");
  cy.get("#id_name").type(name);
  cy.get("#submit-btn").click();
  cy.contains("successfully");
});

Cypress.Commands.add("getDeviceId", () => {
  cy.clearCookies();
  return cy
    .request({
      method: "POST",
      url: "/api/device_id/",
      headers: {
        "Content-Type": "application/json; charset=utf-8",
        cookie: "",
      },
    })
    .then((response) => {
      cy.wrap(response.body.device_id).as("devId");
    });
});

Cypress.Commands.add("createMap", () => {
  cy.visit("/dashboard/maps/new");
  cy.get("#id_name").type("Jukola 2019 - 1st Leg");
  const mapFileName =
    "Jukola_1st_leg_blank_61.45075_24.18994_61.44656_24.24721_61.42094_24.23851_61.42533_24.18156_.jpg";
  cy.get("#id_image").selectFile("cypress/fixtures/" + mapFileName);
  cy.get("button[type='submit']").click();
  cy.url().should("match", /\/dashboard\/maps$/);
});

Cypress.Commands.add("forceVisit", (url) => {
  cy.window().then((win) => {
    return win.open(url, "_self");
  });
});
