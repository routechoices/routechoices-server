context('Cypress tests', () => {
  beforeEach(() => {
    // https://on.cypress.io/visit
    cy.exec('docker exec rc_django /venv/bin/python3 /app/manage.py reset_db_for_tests')
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
      cy.get('#id_slug').clear().type('Jukola-2019-1st-leg')
      cy.get('#id_start_date').type('2019-06-15 20:00:00{enter}')
      cy.get('#id_end_date').type('2019-06-16 10:00:00{enter}')
      cy.get('#id_map').select('Jukola 2019 - 1st Leg (Halden SK)')

      cy.get("input[value='Save']").click()
      cy.url().should('match', /\/dashboard\/event$/)

      cy.forceVisit('/halden-sk/Jukola-2019-1st-leg')
      
      // Create Event with all fields info
      cy.visit('/dashboard/event')
      cy.url().should('match', /\/dashboard\/event$/)
      cy.get('a').contains('Create new event').click()
      cy.url().should('match', /\/dashboard\/event\/new$/)

      cy.get('#id_club').select('Halden SK')
      cy.get('#id_name').type('Jukola 2019 - 1st Leg (2)')
      cy.get('#id_slug').clear().type('Jukola-2019-1st-leg-2')
      cy.get('#id_start_date').type('2019-06-15 20:00:00{enter}')
      cy.get('#id_end_date').type('2019-06-16 00:00:00{enter}')
      cy.get('#id_map').select('Jukola 2019 - 1st Leg (Halden SK)')
      cy.get('#id_competitors-0-device-selectized').type(devId).wait(1000)
      cy.get('#id_competitors-0-name').type('Mats Haldin')
      cy.get('#id_competitors-0-short_name').type('Halden')
      cy.get('#id_competitors-0-start_time').type('2019-06-15 20:00:10{enter}')

      cy.intercept('POST', '/dashboard/event/new').as('eventSubmit');
      cy.get("input[value='Save']").click()
      cy.wait('@eventSubmit').then(({ request, response }) => {
        expect(response.statusCode).to.eq(302);
        expect(request.body).to.contain('&competitors-0-device=1&');
      });
      cy.url().should('match', /\/dashboard\/event$/)
      cy.forceVisit('/halden-sk/Jukola-2019-1st-leg-2')

      // trigger as many errors has possible
      cy.visit('/dashboard/event')
      cy.url().should('match', /\/dashboard\/event$/)
      cy.get('a').contains('Create new event').click()
      cy.url().should('match', /\/dashboard\/event\/new$/)

      cy.get('#id_club').select('Halden SK')
      cy.get('#id_name').type('Jukola 2019 - 1st Leg (2)')
      cy.get('#id_slug').clear().type('Jukola-2019-1st-leg-2')
      cy.get('#id_start_date').type('2019-06-15 20:00:00{enter}')
      cy.get('#id_end_date').type('2019-06-14 00:00:00{enter}')
      cy.get('#id_map_assignations-0-map').select('Jukola 2019 - 1st Leg (Halden SK)')
      cy.get('#id_competitors-0-device-selectized').type(devId).wait(1000)
      cy.get('#id_competitors-0-start_time').type('2019-06-16 20:00:10{enter}')
      cy.get("input[value='Save']").click()
      cy.url().should('match', /\/dashboard\/event\/new$/)
      cy.contains('Start Date must be before End Date')
      cy.contains('Event with this Club and Slug already exists.')
      cy.contains('Event with this Club and Name already exists.')
      cy.contains('Extra maps can be set only if the main map field is set first')
      cy.contains('Competitor start time should be during the event time')
    })
  })
})
