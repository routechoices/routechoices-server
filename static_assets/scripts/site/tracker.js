var dataset = document.currentScript.dataset;
var csrfToken = dataset.csrfToken;
(function () {
  u(".error-message").hide();
  u("#imeiForm").on("submit", function (e) {
    e.preventDefault();
    u("#imeiRes").text(u("#IMEI").val());
    $.ajax({
      type: "POST",
      url: "/api/imei/",
      dataType: "json",
      data: {
        imei: $("#IMEI").val(),
        csrfmiddlewaretoken: csrfToken,
      },
      xhrFields: {
        withCredentials: true,
      },
      crossDomain: true,
    })
      .done(function (response) {
        u("#IMEI").removeClass("is-invalid");
        u("#imeiDevId").removeClass("d-none");
        u(".imeiDevId").text(response.device_id);
        u("#imeiErrorMsg").addClass("d-none");
      })
      .fail(function () {
        u("#imeiErrorMsg").removeClass("d-none");
        u("#IMEI").addClass("is-invalid");
        u("#imeiDevId").addClass("d-none");
      });
  });
})();
