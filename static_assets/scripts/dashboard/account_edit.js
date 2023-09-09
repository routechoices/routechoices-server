(function () {
  u("form").on("submit", function (e) {
    u("#submit-btn").attr({ disabled: true });
    u("#submit-btn i")
      .removeClass("fa-floppy-disk")
      .addClass("fa-spinner fa-spin");
  });
})();
