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
import 'cypress-file-upload';

Cypress.Commands.add("login", (username='admin', password='pa$$word123') => { 
  cy.visit('/accounts/login/')
  cy.get('#id_login').type(username)
  cy.get('#id_password').type(password + '{enter}')
 })

 Cypress.Commands.add("createClub", () => {
  cy.visit('/dashboard/')
  cy.get('a').contains('Clubs').click()
  cy.url().should('match', /\/dashboard\/club$/)
  cy.get('a').contains('Create new club').click()
  cy.url().should('match', /\/dashboard\/club\/new$/)
  cy.get('#id_name').type('Halden SK')
  cy.get('#id_slug').type('halden-sk')
  cy.get('#id_admins').next('').type('admin{enter}')
  cy.get("input[value='Submit']").click()
  cy.url().should('match', /\/dashboard\/club$/)
 })

 Cypress.Commands.add("getDeviceId", () => {
  cy.clearCookies()
  return cy.request({
    method: 'POST',
    url: '/api/device_id/',
    headers: {
      'Content-Type': 'application/json; charset=utf-8',
      cookie: ''
    },
  }).then(response => {
    return cy.wrap(response.body.device_id)
  })
 })

 Cypress.Commands.add("createMap", () => {
  cy.visit('/dashboard/')
  cy.get('a').contains('Maps').click()
  cy.url().should('match', /\/dashboard\/map$/)
  cy.get('a').contains('Create new map').click()
  cy.url().should('match', /\/dashboard\/map\/new$/)
  
  cy.get('#id_club').select('Halden SK')
  cy.get('#id_name').type('Jukola 2019 - 1st Leg')
  const mapFileName = 'Jukola_1st_leg_blank_61.45075_24.18994_61.44656_24.24721_61.42094_24.23851_61.42533_24.18156_.jpg'
  cy.get('#id_image').attachFile(mapFileName)
  cy.get("input[value='Submit']").click()
  cy.url().should('match', /\/dashboard\/map$/)
 })