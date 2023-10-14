document.addEventListener("DOMContentLoaded", function () {
  var $ = django.jQuery;
  $('input[name="_download_gpx_button"]').on("click", function (e) {
    e.preventDefault();
    var encodedData = $("#id_locations_encoded").val();
    var positions = PositionArchive.fromEncoded(encodedData);
    var posArray = positions.getArray();
    let result = `<gpx xmlns="http://www.topografix.com/GPX/1/1" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.topografix.com/GPX/1/1 http://www.topografix.com/GPX/1/1/gpx.xsd" version="1.1" creator="Routechoices.com">
  <metadata/>
  <trk>
    <name></name>
    <desc></desc>
    <trkseg>`;
    posArray.forEach(function (point) {
      result += `
      <trkpt lat="${point.coords.latitude}" lon="${
        point.coords.longitude
      }"><time>${new Date(point.timestamp).toISOString()}</time></trkpt>`;
    });
    result += `
    </trkseg>
  </trk>
</gpx>`;

    var url = "data:text/xml;charset=utf-8," + result;
    var link = document.createElement("a");
    link.download = `device_data.gpx`;
    link.href = url;
    document.body.appendChild(link);
    link.click();
    link.remove();
  });
});
