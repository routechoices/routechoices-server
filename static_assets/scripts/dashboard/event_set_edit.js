(function () {
  makeTextAreasAutoGrow();

  u("#id_create_page").on("change", function (e) {
    if (e.target.checked) {
      u("#id_slug").parent().show();
      u("#id_slug").attr("required", true);
      u("#id_list_secret_events").parent().show();
      u("#id_description").parent().parent().show();
    } else {
      u("#id_slug").parent().hide();
      u("#id_slug").attr("required", false);
      u("#id_list_secret_events").parent().hide();
      u("#id_description").parent().parent().hide();
    }
  });

  u("#id_slug").parent().find(".form-label").text("Domain Prefix");

  var slugPrefix = u(
    '<br/><span id="id_slug-prefix" class="pe-2" style="color: #999">' +
      window.local.clubUrl +
      "</span>"
  );
  u("#id_slug").before(slugPrefix);
  var slugPrefixWidth = document
    .getElementById("id_slug-prefix")
    .getBoundingClientRect().width;
  u("#id_slug").css({
    width: "calc(100% - " + slugPrefixWidth + "px)",
    "min-width": "150px",
    display: "inline-block",
  });
  u("#id_slug").parent().find(".form-label").text("URL");
  u("#id_slug").attr("required", true);

  makeFieldRandomizable("#id_slug");

  if (!u("#id_create_page").nodes[0].checked) {
    u("#id_slug").parent().hide();
    u("#id_slug").attr("required", false);
    u("#id_list_secret_events").parent().hide();
    u("#id_description").parent().parent().hide();
  }
})();
