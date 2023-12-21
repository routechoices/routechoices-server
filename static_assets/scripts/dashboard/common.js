var makeFieldRandomizable = function (id) {
  u(id)
    .parent()
    .find(".form-text")
    .text("")
    .append(
      '<button class="randomize_btn btn btn-info btn-sm float-end py-1 px-2" type="button"><i class="fa-solid fa-shuffle"></i> Randomize</button>'
    );
  u(".randomize_btn").on("click", function (e) {
    e.preventDefault();
    var target = u(this).parent().parent().find(".form-control");
    var result = "";
    var characters = "23456789abcdefghijkmnpqrstuvwxyz";
    var charactersLength = characters.length;
    for (var i = 0; i < 6; i++) {
      result += characters.charAt(Math.floor(Math.random() * charactersLength));
    }
    target.val(result);
    target.trigger("blur");
  });
};

var makeFieldNowable = function (el) {
  var localTimeDisplay = u(el).parent().find(".local_time");
  localTimeDisplay.before(
    '<button class="set_time_now_btn btn btn-info btn-sm py-1 px-2 float-end" type="button"><i class="fa-solid fa-clock"></i> Set Now</button>'
  );
  u(el)
    .parent()
    .find(".set_time_now_btn")
    .on("click", function (e) {
      e.preventDefault();
      var target = u(this).parent().parent().find("input");
      target.val(dayjs().utc().format("YYYY-MM-DD HH:mm:ss"));
      target.trigger("change");
    });
};

var makeTimeFieldClearable = function (el) {
  var localTimeDisplay = u(el).parent().find(".local_time");
  localTimeDisplay.before(
    '<button class="set_time_null_btn btn btn-info btn-sm ms-1 py-1 px-2 float-end" type="button"><i class="fa-solid fa-xmark"></i> Clear</button>'
  );
  u(el)
    .parent()
    .find(".set_time_null_btn")
    .on("click", function (e) {
      e.preventDefault();
      var target = u(this).parent().parent().find("input");
      target.val("");
      target.trigger("change");
    });
};

var makeTextAreasAutoGrow = function () {
  u("textarea").wrap('<div class="grow-wrap"/>');
  u("textarea").each(function (el) {
    el.addEventListener("input", (e) => {
      e.target.parentNode.dataset.replicatedValue = e.target.value;
    });
    u(el).trigger("input");
  });
};
