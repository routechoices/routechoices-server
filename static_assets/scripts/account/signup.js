(function () {
  u("form").on("submit", function (e) {
    u("#submit-btn").attr({ disabled: true });
    u("#submit-btn i")
      .removeClass("fa-user-plus")
      .addClass("fa-spinner fa-spin");
  });
})();
