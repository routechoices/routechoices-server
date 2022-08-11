var extractCornersCoordsFromFilename = function (filename) {
  var re = /(_\d+\.\d+){8}_\.(gif|png|jpg|jpeg|webp)$/gi;
  var found = filename.match(re);
  if (!found) {
    return false;
  } else {
    var coords = found[0].split("_");
    coords.pop();
    coords.shift();
    return coords.join(",");
  }
};
(function () {
  u("#id_image").attr(
    "accept",
    "image/png,image/jpeg,image/gif,image/webp,image/avif"
  );
  u("#id_image").on("change", function () {
    if (this.files.length > 0 && this.files[0].size > 1e7) {
      swal({
        title: "Error!",
        text: "File is too big!",
        type: "error",
        confirmButtonText: "OK",
      });
      this.value = "";
    }
    if (this.files.length > 0 && this.value) {
      var bounds = extractCornersCoordsFromFilename(this.files[0].name);
      if (bounds && !u("#id_corners_coordinates").val()) {
        u("#id_corners_coordinates").val(bounds);
      }
      u("#calibration_help").removeClass("hidden");
    } else {
      u("#calibration_help").addClass("hidden");
    }
  });
})();
