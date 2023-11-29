(function () {
  u("form").on("submit", function (e) {
    var t = u(this);
    var submitBtn = t.find("#submit-btn");
    var icon = submitBtn.find("i");
    submitBtn.attr({ disabled: true });
    icon.attr({ class: "" }).addClass("fa-solid fa-spinner fa-spin");
  });
})();
