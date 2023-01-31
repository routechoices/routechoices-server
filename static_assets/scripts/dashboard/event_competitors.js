var seletizeOptions = {
  valueField: "id",
  labelField: "device_id",
  searchField: "device_id",
  create: false,
  createOnBlur: false,
  persist: false,
  plugins: ["preserve_on_blur", "change_listener"],
  load: function (query, callback) {
    if (query.length < 4) {
      return callback();
    }
    reqwest({
      url:
        window.local.apiBaseUrl +
        "search/device?q=" +
        encodeURIComponent(query),
      method: "get",
      type: "json",
      withCredentials: true,
      crossOrigin: true,
      success: function (res) {
        callback(res.results);
      },
      error: function () {
        callback();
      },
    });
  },
};

var lastDeviceSelectInput = null;

function showLocalTime(el) {
  var val = u(el).val();
  if (val) {
    var local = dayjs(val).utc(true).local().format("YYYY-MM-DD HH:mm:ss");
    u(el)
      .parent()
      .find(".local_time")
      .text(local + " Local time");
  } else {
    u(el).parent().find(".local_time").text("");
  }
}

(function () {
  u(".datetimepicker").map(function (el) {
    var options = {
      useCurrent: false,
      display: {
        components: {
          useTwentyfourHour: true,
          seconds: true,
        },
      },
    };
    var val = u(el).val();
    if (val) {
      val = val.substring(0, 10) + "T" + val.substring(11, 19) + "Z";
      options.defaultDate = new Date(
        new Date(val).toLocaleString("en-US", { timeZone: "UTC" })
      );
    }
    new tempusDominus.TempusDominus(el, options);
  });
  u('label[for$="-DELETE"]').parent(".form-group").hide();
  $(".formset_row").formset({
    addText: "",
    deleteText: '<i class="fa-solid fa-trash-can fa-2x"></i>',
    prefix: "competitors",
  });
  u(".dynamic-form-add").hide();
  // next line must come after formset initialization
  var hasArchivedDevices = false;
  u('select[name$="-device"]').each(function (el) {
    if (el.options[el.selectedIndex].text.endsWith("*")) {
      hasArchivedDevices = true;
    }
    new TomSelect(el, seletizeOptions);
  });
  if (hasArchivedDevices) {
    u(".table-bottom").before(
      '<div class="form-text"><span>* Archive of original device</span></div>'
    );
  }

  u(".datetimepicker").each(function (el) {
    u(el).attr("autocomplete", "off");
    showLocalTime(el);
    el.addEventListener(tempusDominus.Namespace.events.change, function (e) {
      showLocalTime(e.target);
    });
  });

  var utcOffset = dayjs().utcOffset();
  var utcOffsetText =
    (utcOffset > 0 ? "+" : "-") +
    ("0" + Math.floor(Math.abs(utcOffset / 60))).slice(-2) +
    ":" +
    ("0" + Math.round(utcOffset % 60)).slice(-2);
  u(".utc-offset").text("(UTC Offset " + utcOffsetText + ")");
})();
