(function () {
  var $gpxUploader = u("#id_gpx_file");
  $gpxUploader.attr("accept", ".gpx");
  $gpxUploader.on("change", function () {
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
