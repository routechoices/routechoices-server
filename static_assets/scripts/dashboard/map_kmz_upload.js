(function () {
  var $field = u("#id_file");
  $field.attr("accept", ".kml, .kmz");
  $field.on("change", async function () {
    if (this.files.length > 0 && this.files[0].size > 2 * 1e7) {
      swal({
        title: "Error!",
        text: "File is too big!",
        type: "error",
        confirmButtonText: "OK",
      });
      this.value = "";
    }
    if (this.files.length > 0) {
      try {
        var zip = await JSZip.loadAsync(this.files[0]);
        if (zip.files && zip.files["doc.kml"]) {
          const kml = await zip.file("doc.kml").async("string");
          const parser = new DOMParser();
          const parsedText = parser.parseFromString(kml, "text/xml");
          const nLayers =
            parsedText.getElementsByTagName("GroundOverlay").length;
          swal({
            title: "Info",
            text:
              "File contains " +
              nLayers +
              " map" +
              (nLayers != 1 ? "s" : "") +
              "!",
            type: "info",
            confirmButtonText: "OK",
          });
        }
      } catch {
        swal({
          title: "Error!",
          text: "Invalid KMZ!",
          type: "error",
          confirmButtonText: "OK",
        });
        this.value = "";
      }
    }
  });
})();
