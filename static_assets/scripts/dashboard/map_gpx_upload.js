(function () {
  var $field = u("#id_gpx_file");
  $field.attr("accept", ".gpx");
  $field.on("change", function () {
    if (this.files.length > 0 && this.files[0].size > 2 * 1e7) {
      swal({
        title: "Error!",
        text: "File is too big!",
        type: "error",
        confirmButtonText: "OK",
      });
      this.value = "";
    }
  });

  u("form").on("submit", function (e) {
    u("#submit-btn").attr({ disabled: true });
    u("#submit-btn i")
      .removeClass("fa-file-arrow-up")
      .addClass("fa-spinner fa-spin");
  });
})();
