context('Cypress tests', () => {
  beforeEach(() => {
    // https://on.cypress.io/visit
    cy.visit('/')
  })

  it('Create an Event', function () {
    cy.login()
    cy.url().should('include', '/dashboard/')

    // Create club
    cy.visit('/dashboard')
    cy.get('a').contains('Clubs').click()
    cy.url().should('include', '/dashboard/club')
    cy.get('a').contains('Create new club').click()
    cy.url().should('include', '/dashboard/club/new')
    cy.get('#id_name').type('Halden SK')
    cy.get('#id_slug').type('halden-sk')
    cy.get('#id_admins').next('').type('admin{enter}')
    cy.get("input[value='Submit']").click()
    cy.url().should('include', '/dashboard/club')

    // Create Map
    cy.visit('/dashboard')
    cy.get('a').contains('Maps').click()
    cy.url().should('include', '/dashboard/map')
    cy.get('a').contains('Create new map').click()
    cy.url().should('include', '/dashboard/map/new')
    
    cy.get('#id_club').select('Halden SK')
    cy.get('#id_name').type('Jukola 2019 - 1st Leg')
    const mapFileName = 'Jukola_1st_leg_blank_61.45075_24.18994_61.44656_24.24721_61.42094_24.23851_61.42533_24.18156_.jpg'
    cy.get('#id_image').attachFile(mapFileName)
    cy.get("input[value='Submit']").click()
    cy.url().should('include', '/dashboard/map')

    // Create Event
    cy.visit('/dashboard/event')
    cy.url().should('include', '/dashboard/event')
    cy.get('a').contains('Create new event').click()
    cy.url().should('include', '/dashboard/event/new')

    cy.get('#id_club').select('Halden SK')
    cy.get('#id_name').type('Jukola 2019 - 1st Leg')
    cy.get('#id_slug').type('Jukola-2019-1st-leg')
    cy.get('#id_start_date').type('2019-06-15 20:00:00{enter}')
    cy.get('#id_end_date').type('2019-06-16 00:00:00{enter}')
    cy.get('#id_map').select('Jukola 2019 - 1st Leg (Halden SK)')

    cy.get("input[value='Submit']").click()
    cy.url().should('include', '/dashboard/event')
    cy.visit('/halden-sk/Jukola-2019-1st-leg')
  })
})