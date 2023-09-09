(function () {
  u("form").on("submit", function (e) {
    u("#submit-btn").attr({ disabled: true });
    u("#submit-btn i")
      .removeClass("fa-right-to-bracket")
      .addClass("fa-spinner fa-spin");
  });
})();
