(function () {
  var feedback = u("input[type='password']").hasClass("is-invalid");
  u("input[type='password']").wrap(
    `<div class="input-group${feedback ? " is-invalid" : ""}">`
  );
  u("input[type='password']").after(
    '<span class="input-group-text togglePassword" style="cursor: pointer"><i class="fa-regular fa-fw fa-eye"></i></span>'
  );
  u(".togglePassword").on("click", function (e) {
    u(this).find("i").toggleClass("fa-eye-slash, fa-eye");
    u(this)
      .parent()
      .find("input")
      .each(function (el) {
        el.type = el.type == "password" ? "text" : "password";
      });
  });
})();
