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
function onAddedCompetitorRow(row) {
  var options = {
    useCurrent: false,
    display: {
      components: {
        useTwentyfourHour: true,
        seconds: true,
      },
    },
  };
  var el = u(row).find(".datetimepicker").first();
  new tempusDominus.TempusDominus(el, options);
  u(row)
    .find('select[name$="-device"]')
    .each(function (el) {
      lastDeviceSelectInput = new TomSelect(el, seletizeOptions);
    });

  u(el).attr("autocomplete", "off");
  showLocalTime(el);
  el.addEventListener(tempusDominus.Namespace.events.change, function (e) {
    showLocalTime(e.target);
  });
}

function onCsvParsed(result) {
  u("#csv_input").val("");
  var errors = "";
  if (result.errors.length > 0) {
    errors = "No line found";
  }
  if (!errors) {
    result.data.forEach(function (l) {
      var empty = false;
      if (l.length == 1 && l[0] == "") {
        empty = true;
      }
      if (!empty && l.length != 4) {
        errors = "Each row should have 4 columns";
      } else {
        if (!empty && l[2]) {
          try {
            new Date(l[2]);
          } catch (e) {
            errors = "One row contains an invalid date";
          }
        }
      }
    });
  }
  if (errors) {
    swal({
      title: "Error!",
      text: "Could not parse this file: " + errors,
      type: "error",
      confirmButtonText: "OK",
    });
    return;
  } // clear empty lines
  u(".formset_row").each(function (e) {
    if (
      u(e)
        .find("input")
        .filter(function (el) {
          return u(el).attr("type") != "hidden" && el.value != "";
        }).length == 0
    ) {
      u(e).find(".delete-row").first().click();
    }
  });
  result.data.forEach(function (l) {
    u(".add-competitor-btn").first().click();
    if (l.length != 1) {
      var inputs = u(u(".formset_row").last()).find("input").nodes;
      if (l.length > 3) {
        var myDeviceSelectInput = lastDeviceSelectInput;
        reqwest({
          url: window.local.apiBaseUrl + "search/device?q=" + l[3],
          method: "get",
          type: "json",
          withCredentials: true,
          crossOrigin: true,
          success: (function (line) {
            return function (res) {
              if (res.results.length == 1) {
                var r = res.results[0];
                myDeviceSelectInput.addOption(r);
                myDeviceSelectInput.setValue(r[seletizeOptions.valueField]);
              }
            };
          })(),
        });
      }
      if (l[2]) {
        inputs[5].value = dayjs(l[2]).utc().format("YYYY-MM-DD HH:mm:ss");
        u(inputs[5]).trigger("change");
      }
      inputs[3].value = l[0];
      inputs[4].value = l[1];
    }
  });
  u(".add-competitor-btn").first().click();
}

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
    new tempusDominus.TempusDominus(el, options);
    if (
      val &&
      /^\d{4}-\d{2}-\d{2}/.test(val) &&
      /\d{2}:\d{2}:\d{2}$/.test(val)
    ) {
      val = val.substring(0, 10) + " " + val.substring(11, 19);
      u(el).val(val);
      u(el).trigger("change");
    } else {
      u(el).val("");
    }
    
  });
  u('label[for$="-DELETE"]').parent(".form-group").hide();
  $(".formset_row").formset({
    addText: '<i class="fa fa-plus-circle"></i> Add Competitor',
    addCssClass: "btn btn-primary add-competitor-btn",
    deleteText: '<i class="fa fa-trash fa-2x"></i>',
    prefix: "competitors",
    added: onAddedCompetitorRow,
  });
  $(".extra_map_formset_row").formset({
    addText: '<i class="fa fa-plus-circle"></i> Add Map',
    addCssClass: "btn btn-primary add-map-btn",
    deleteText: '<i class="fa fa-trash fa-2x"></i>',
    prefix: "map_assignations",
    formCssClass: "extra_map_formset_row",
  });

  // next line must come after formset initialization
  var hasArchivedDevices = false;
  u('select[name$="-device"]').each(function (el) {
    if (el.options[el.selectedIndex].text.endsWith("*")) {
      hasArchivedDevices = true;
    }
    new TomSelect(el, seletizeOptions);
  });
  if (hasArchivedDevices) {
    u(".add-competitor-btn")
      .parent()
      .append(
        '<div class="form-text"><span>* Archive of original device</span></div>'
      );
  }

  var originalEventStart = u("#id_start_date").val();
  var competitorsStartTimeElsWithSameStartAsEvents = u(
    ".competitor_table .datetimepicker"
  ).filter(function (el) {
    return originalEventStart !== "" && u(el).val() == originalEventStart;
  }).nodes;
  u("#csv_input").on("change", function (e) {
    Papa.parse(e.target.files[0], { complete: onCsvParsed });
  });
  u(".datetimepicker").each(function (el) {
    u(el).attr("autocomplete", "off");
    showLocalTime(el);
    el.addEventListener(tempusDominus.Namespace.events.change, function (e) {
      var elId = u(e.target).attr("id");
      competitorsStartTimeElsWithSameStartAsEvents = u(
        competitorsStartTimeElsWithSameStartAsEvents
      ).filter(function (_e) {
        return u(_e).attr("id") != elId;
      }).nodes;
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

  u("#id_start_date")
    .first()
    .addEventListener(tempusDominus.Namespace.events.change, function (e) {
      var newValue = u(e.target).val();
      u(competitorsStartTimeElsWithSameStartAsEvents).each(function (el) {
        u(el).val(newValue);
      });
    });

  var tailLength = u("#id_tail_length").addClass("d-none").val();
  u('[for="id_tail_length"]').text("Tail length (Hours, Minutes, Seconds)");
  var tailLengthInput = u(
    '<div class="row g-3">' +
      '<div class="col-auto"><input type="number" min="0" max="9999" class="form-control tailLengthControl" id="tailLengthHoursInput" value="' +
      Math.floor(tailLength / 3600) +
      '" style="width:100px"/></div><div class="col-auto" style="vertical-align: bottom;margin:1.3em -.7em">:</div>' +
      '<div class="col-auto"><input type="number" min="0" max="59" class="form-control tailLengthControl" id="tailLengthMinutesInput" value="' +
      (Math.floor(tailLength / 60) % 60) +
      '" style="width:75px"/></div><div class="col-auto" style="vertical-align: bottom;margin:1.3em -.7em">:</div>' +
      '<div class="col-auto"><input type="number" min="0" max="59" class="form-control tailLengthControl" id="tailLengthSecondsInput" value="' +
      (tailLength % 60) +
      '" style="width:75px"/></div>' +
      "</div>"
  );
  u("#id_tail_length").after(tailLengthInput);
  u(tailLengthInput)
    .find(".tailLengthControl")
    .on("input", function (e) {
      var h = parseInt(u("#tailLengthHoursInput").val() || 0);
      var m = parseInt(u("#tailLengthMinutesInput").val() || 0);
      var s = parseInt(u("#tailLengthSecondsInput").val() || 0);
      var v = 3600 * h + 60 * m + s;
      if (isNaN(v)) {
        return;
      }
      tailLength = Math.max(0, v);
      u("#id_tail_length").val(tailLength);
      u("#tailLengthHoursInput").val(Math.floor(tailLength / 3600));
      u("#tailLengthMinutesInput").val(Math.floor((tailLength / 60) % 60));
      u("#tailLengthSecondsInput").val(Math.floor(tailLength % 60));
    });

  u('[for="id_start_date"]').after(
    '<button id="set_start_date_now_btn" class="btn btn-success btn-sm" style="padding: 3px 8px;margin-left: 15px;"><i class="fa-solid fa-clock"></i> Set Now</button>'
  );
  u('[for="id_end_date"]').after(
    '<button id="set_end_date_now_btn" class="btn btn-success btn-sm" style="padding: 3px 8px;margin-left: 15px;"><i class="fa-solid fa-clock"></i> Set Now</button>'
  );
  u("#set_start_date_now_btn").on("click", function (e) {
    e.preventDefault();
    var el = "#id_start_date";
    u(el).val(dayjs().utc().format("YYYY-MM-DD HH:mm:ss"));
    u(el).trigger("change");
  });
  u("#set_end_date_now_btn").on("click", function (e) {
    e.preventDefault();
    var el = "#id_end_date";
    u(el).val(dayjs().utc().format("YYYY-MM-DD HH:mm:ss"));
    u(el).trigger("change");
  });
})();
