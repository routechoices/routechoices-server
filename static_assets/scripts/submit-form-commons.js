(function () {
  u("form").on("submit", function (e) {
    var t = u(this);
    var submitBtn = t.find("#submit-btn");
    var icon = submitBtn.find("i");
    submitBtn.attr({ disabled: true });
    icon.attr({ class: "" }).addClass("fa-solid fa-spinner fa-spin");
  });

  u("input[name=type-confirmation]").on("keyup", function (ev) {
    var t = u(this).parent().parent();
    var submitBtn = t.find("#submit-btn");
    if (ev.target.value === "DELETE") {
      submitBtn.attr({ disabled: false });
    } else {
      submitBtn.attr({ disabled: true });
    }
  });
})();
