context('Cypress tests', () => {
  beforeEach(() => {
    // https://on.cypress.io/visit
    cy.visit('/')
  })

  it('Test Login', function () {
    cy.visit('/accounts/login/')
    cy.get('#id_login')
      .type('admin')
    cy.get('#id_password')
      .type('pa$$word123{enter}')
    cy.url().should('include', '/dashboard/')
  })
})