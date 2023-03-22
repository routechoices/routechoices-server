(function () {
  u("input[type='password']").after(
    '<span class="input-group-text togglePassword"><i class="fa-regular fa-eye-slash"></i></span>'
  ).parent().addClass("input-group");
  u(".togglePassword").on("click", function (e) {
    u(e.target).toggleClass("fa-eye", "fa-eye-slash");
    u(e.target)
      .parent()
      .find("input")
      .each(function (el) {
        el.type = el.type == "password" ? "text" : "password";
      });
  });
})();
