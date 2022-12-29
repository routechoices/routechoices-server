pdfjsLib.GlobalWorkerOptions.workerSrc =
  "//www.routechoices.com/static/vendor/pdfjs-2.7.570/pdf.worker.min.js";

var extractCornersCoordsFromFilename = function (filename) {
  var re = /(_[-]?\d+(\.\d+)?){8}_\.(gif|png|jpg|jpeg|webp)$/gi;
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
var onPDF = function (ev, filename) {
  var loadingTask = pdfjsLib.getDocument({
    data: new Uint8Array(ev.target.result),
  });
  loadingTask.promise.then(function (pdf) {
    pdf.getPage(1).then(function (page) {
      var PRINT_RESOLUTION = 300;
      var PRINT_UNITS = PRINT_RESOLUTION / 72.0;
      var CSS_UNITS = 96.0 / 72.0;
      var viewport = page.getViewport({ scale: 1 });
      var width = Math.floor(viewport.width * CSS_UNITS) + "px";
      var height = Math.floor(viewport.height * CSS_UNITS) + "px";

      // Prepare canvas using PDF page dimensions
      var canvas = document.createElement("canvas");
      canvas.height = Math.floor(viewport.height * PRINT_UNITS);
      canvas.width = Math.floor(viewport.width * PRINT_UNITS);
      var context = canvas.getContext("2d");
      // Render PDF page into canvas context
      var renderContext = {
        canvasContext: context,
        transform: [PRINT_UNITS, 0, 0, PRINT_UNITS, 0, 0],
        viewport: viewport,
      };
      var renderTask = page.render(renderContext);
      renderTask.promise.then(function () {
        var ext = filename.split(".").pop();
        filename = filename.slice(0, filename.length - ext.length) + "jpg";
        canvas.toBlob(
          function (blob) {
            var file = new File([blob], filename, {
              type: "image/jpeg",
              lastModified: new Date().getTime(),
            });
            var container = new DataTransfer();
            container.items.add(file);
            u("#id_image").nodes[0].files = container.files;
            u("#id_image").trigger("change");
          },
          "image/jpeg",
          0.8
        );
      });
    });
  });
};

(function () {
  u("#id_image").attr(
    "accept",
    "image/png,image/jpeg,image/gif,image/webp,application/pdf"
  );
  u("#id_image").on("change", function () {
    if (this.files.length > 0 && this.files[0].size > 2 * 1e7) {
      swal({
        title: "Error!",
        text: "File is too big!",
        type: "error",
        confirmButtonText: "OK",
      });
      this.value = "";
    }
    if (this.files.length > 0 && this.value) {
      if (this.files[0].type == "application/pdf") {
        var pdfFile = this.files[0];
        var pdfFileReader = new FileReader();
        pdfFileReader.onload = function (ev) {
          onPDF(ev, pdfFile.name);
        };
        pdfFileReader.readAsArrayBuffer(pdfFile);
        return;
      }
      var bounds = extractCornersCoordsFromFilename(this.files[0].name);
      if (bounds && !u("#id_corners_coordinates").val()) {
        u("#id_corners_coordinates").val(bounds);
      }
      u("#calibration_help").removeClass("d-none");
      u("#id_corners_coordinates").trigger("change");
    } else {
      u("#calibration_help").addClass("d-none");
      u("#calibration_preview").addClass("d-none");
    }
  });

  u("#id_corners_coordinates").on("change", function (e) {
    var val = e.target.value;
    var re = /[-]?\d+(\.\d+)?(,[-]?\d+(\.\d+)?){7}$/gi;
    var found = val.match(re);
    console.log(found, u("#id_image").val());
    if (found && u("#id_image").val()) {
      u("#calibration_preview").removeClass("d-none");
    } else {
      u("#calibration_preview").addClass("d-none");
    }
  });
})();
