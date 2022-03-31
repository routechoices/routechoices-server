(function () {
  u(".error-message").hide();

  u("#imeiForm").on("submit", function (e) {
    e.preventDefault();
    u("#imeiRes").text(u("#IMEI").val());
    reqwest({
      url: "/api/imei/",
      method: "post",
      data: {
        imei: u("#IMEI").val(),
        csrfmiddlewaretoken: csrfToken,
      },
      type: "json",
      withCredentials: true,
      crossOrigin: true,
      success: function (response) {
        u("#IMEI").removeClass("is-invalid");
        u("#imeiDevId").removeClass("d-none");
        u(".imeiDevId").text(response.device_id);
        u("#imeiErrorMsg").addClass("d-none");
        u("#copyDevIdBtn").off("click");
        u("#copyDevIdBtn").on("click", function () {
          navigator.clipboard.writeText(response.device_id);
        });
      },
      error: function (req) {
        u("#imeiErrorMsg").removeClass("d-none");
        u("#IMEI").addClass("is-invalid");
        u("#imeiDevId").addClass("d-none");
        try {
          u("#imeiErrorMsg").html(
            '<i class="fa fa-warning"></i> ' +
              u("<div/>").text(JSON.parse(req.responseText)[0]).text()
          );
        } catch {}
      },
    });
  });
})();
