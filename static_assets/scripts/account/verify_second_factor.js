(function () {
  u("form").on("submit", function (e) {
    var btn = u(e.target).find(".submit-btn");
    btn.addClass("disabled");
    btn.prepend('<i class="fa-solid fa-spinner fa-spin me-1"></i>');
  });
  u("#id_token")
    .addClass("font-monospace")
    .attr({
      placeholder: "••••••",
      maxLength: 6,
    })
    .on("input", function () {
      this.value = this.value.replace(/[^0-9]/g, "");
      if (this.value.length >= 6)
        u(this).parent().parent().find("button").first().focus();
    });
})();
