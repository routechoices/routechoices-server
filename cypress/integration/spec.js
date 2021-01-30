context('Cypress tests', () => {
  beforeEach(() => {
    // https://on.cypress.io/visit
    cy.exec('docker exec dz01 /venv/bin/python3 /app/manage.py reset_db_for_tests')
    cy.visit('/')
  })

  it('Create an Event', function () {
    cy.getDeviceId().then(devId => {
      cy.login()
      cy.url().should('match', /\/dashboard\/$/)


      // Create club
      cy.createClub()

      // Create Map
      cy.createMap()

      // Create Event with minimal info
      cy.visit('/dashboard/event')
      cy.url().should('match', /\/dashboard\/event$/)
      cy.get('a').contains('Create new event').click()
      cy.url().should('match', /\/dashboard\/event\/new$/)

      cy.get('#id_club').select('Halden SK')
      cy.get('#id_name').type('Jukola 2019 - 1st Leg')
      cy.get('#id_slug').type('Jukola-2019-1st-leg')
      cy.get('#id_start_date').type('2019-06-15 20:00:00{enter}')
      cy.get('#id_map').select('Jukola 2019 - 1st Leg (Halden SK)')

      cy.get("input[value='Submit']").click()
      cy.url().should('match', /\/dashboard\/event$/)
      cy.visit('/halden-sk/Jukola-2019-1st-leg')

      // Create Event with all fields info
      cy.visit('/dashboard/event')
      cy.url().should('match', /\/dashboard\/event$/)
      cy.get('a').contains('Create new event').click()
      cy.url().should('match', /\/dashboard\/event\/new$/)

      cy.get('#id_club').select('Halden SK')
      cy.get('#id_name').type('Jukola 2019 - 1st Leg (2)')
      cy.get('#id_slug').type('Jukola-2019-1st-leg-2')
      cy.get('#id_start_date').type('2019-06-15 20:00:00{enter}')
      cy.get('#id_end_date').type('2019-06-16 00:00:00{enter}')
      cy.get('#id_map').select('Jukola 2019 - 1st Leg (Halden SK)')
      cy.get('#id_competitors-0-device-selectized').type(devId)
      cy.get('#id_competitors-0-name').type('Mats Haldin')
      cy.get('#id_competitors-0-short_name').type('Halden')
      cy.get('#id_competitors-0-start_time').type('2019-06-15 20:00:10{enter}')
      
      cy.get("input[value='Submit']").click()
      cy.url().should('match', /\/dashboard\/event$/)
      cy.visit('/halden-sk/Jukola-2019-1st-leg-2')
    })
  })
})