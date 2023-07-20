(function () {
  u("#id_create_page").on("change", function (e) {
    if (e.target.checked) {
      u("#id_slug").parent().show();
      u("#id_slug").attr("required", true);
      u("#id_list_secret_events").parent().show();
      u("#id_description").parent().show();
    } else {
      u("#id_slug").parent().hide();
      u("#id_slug").attr("required", false);
      u("#id_list_secret_events").parent().hide();
      u("#id_description").parent().hide();
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
  u("#id_slug")
    .parent()
    .find(".form-text")
    .text("")
    .append(
      '<button class="randomize_btn btn btn-info btn-sm float-end py-1 px-2"><i class="fa-solid fa-shuffle"></i> Randomize</button>'
    );
  u(".randomize_btn").on("click", function (e) {
    e.preventDefault();
    var target = u(e.target).parent().parent().find(".form-control");
    var result = "";
    var characters = "23456789abcdefghijkmnpqrstuvwxyz";
    var charactersLength = characters.length;
    for (var i = 0; i < 6; i++) {
      result += characters.charAt(Math.floor(Math.random() * charactersLength));
    }
    target.val(result);
    target.trigger("blur");
  });

  u("#id_slug").attr("required", true);
  if (!u("#id_create_page").nodes[0].checked) {
    u("#id_slug").parent().hide();
    u("#id_slug").attr("required", false);
    u("#id_list_secret_events").parent().hide();
    u("#id_description").parent().hide();
  }
})();
