(function () {
  var $field = u("#id_gpx_file");
  $field.attr("accept", ".gpx");
  $field.on("change", function () {
    if (this.files.length > 0 && this.files[0].size > 1e7) {
      swal({
        title: "Error!",
        text: "File is too big!",
        type: "error",
        confirmButtonText: "OK",
      });
      this.value = "";
    }
  });
})();
