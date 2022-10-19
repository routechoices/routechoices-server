beforeEach(function () {
  cy.log("I run before every test in every spec file!!!!!!");
  window.sessionStorage.clear();
  window.localStorage.clear();
  cy.wait(1000);
});
