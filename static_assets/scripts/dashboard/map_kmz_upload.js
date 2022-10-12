(function () {
  var $field = u("#id_file");
  $field.attr("accept", ".kml, .kmz");
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
})();
