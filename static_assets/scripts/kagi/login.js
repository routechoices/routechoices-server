(function () {
  u("input[type='password']")
    .wrap('<div class="input-group mb-3"></div>')
  u("input[type='password']").after(
      '<span class="input-group-text togglePassword" style="cursor: pointer"><i class="fa-regular fa-fw fa-eye"></i></span>'
    )
  u(".togglePassword").on("click", function (e) {
    u(e.target).parent().find('i').toggleClass("fa-eye-slash", "fa-eye");
    u(e.target).parent()
      .parent()
      .find("input")
      .each(function (el) {
        el.type = el.type == "password" ? "text" : "password";
      });
  });
})();
