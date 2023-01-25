before(function () {
  cy.exec("docker exec rc_django python /app/manage.py reset_db_for_e2e_tests");
});
