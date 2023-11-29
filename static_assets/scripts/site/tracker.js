(function () {
  u(".error-message").hide();
  u("#imeiForm").on("submit", function (e) {
    e.preventDefault();

    var submitBtn = u("#submit-btn");
    submitBtn.attr({ disabled: true });

    u("#imeiRes").text(u("#IMEI").val());
    reqwest({
      url: "/api/device/",
      method: "post",
      data: {
        imei: u("#IMEI").val(),
        csrfmiddlewaretoken: window.local.csrfToken,
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
        u("#copyDevIdBtn").on("click", function (ev) {
          var tooltip = new bootstrap.Tooltip(ev.currentTarget, {
            placement: "right",
            title: "copied",
          });
          tooltip.show();
          navigator.clipboard.writeText(response.device_id);
          setTimeout(function () {
            tooltip.dispose();
          }, 750);
        });
      },
      error: function (req) {
        u("#imeiErrorMsg").removeClass("d-none");
        u("#IMEI").addClass("is-invalid");
        u("#imeiDevId").addClass("d-none");
        try {
          u("#imeiErrorMsg").html(
            '<i class="fa-solid fa-triangle-exclamation"></i> ' +
              u("<div/>").text(JSON.parse(req.responseText)[0]).text()
          );
        } catch {}
      },
      complete: function () {
        submitBtn.attr({ disabled: false });
      },
    });
  });
})();
