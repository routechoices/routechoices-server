beforeEach(function () {
  cy.log("I run before every test in every spec file!!!!!!");
  window.sessionStorage.clear();
  window.localStorage.clear();
  //cy.exec(`./da reset_db_for_tests`);
  cy.wait(1000);
});
