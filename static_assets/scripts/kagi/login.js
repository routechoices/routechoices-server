(function () {
  u("input[type='password']")
    .wrap('<div class="input-group mb-3"></div>')
  u("input[type='password']").after(
      '<span class="input-group-text togglePassword"><i class="fa-regular fa-eye-slash"></i></span>'
    )
  u(".togglePassword").on("click", function (e) {
    u(e.target).find('i').toggleClass("fa-eye", "fa-eye-slash");
    u(e.target)
      .parent()
      .find("input")
      .each(function (el) {
        el.type = el.type == "password" ? "text" : "password";
      });
  });
})();
