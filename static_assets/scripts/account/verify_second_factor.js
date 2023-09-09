(function () {
  u("form").on("submit", function (e) {
    var btn = u(e.target).find(".submit-btn");
    btn.addClass("disabled");
    btn.prepend('<i class="fa-solid fa-spinner fa-spin me-1"></i>');
  });
})();
