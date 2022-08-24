pdfjsLib.GlobalWorkerOptions.workerSrc =
  "//www.routechoices.com/static/vendor/pdfjs-2.7.570/pdf.worker.min.js";

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
            saveAs(blob, filename);
            u("#step1").hide();
            u("#step2").show();
          },
          "image/jpeg",
          0.8
        );
      });
    });
  });
};
(function () {
  u("#step2").hide();
  u("#pdfInputFile").on("change", function (ev) {
    var file = ev.target.files[0];
    var fr = new FileReader();
    fr.onload = function (ev) {
      onPDF(ev, file.name);
    };
    fr.readAsArrayBuffer(file);
  });
})();
