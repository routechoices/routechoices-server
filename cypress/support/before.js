before(function () {
  cy.exec(
    "docker exec rc_django /venv/bin/python3 /app/manage.py reset_db_for_e2e_tests"
  );
});
