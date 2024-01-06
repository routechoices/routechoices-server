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

  u(row)
    .find('input[id$="-start_time"]')
    .each((el) => {
      makeTimeFieldClearable(el);
      makeFieldNowable(el);
    });

  u(el).attr("autocomplete", "off");
  showLocalTime(el);
  el.addEventListener(tempusDominus.Namespace.events.change, function (e) {
    showLocalTime(e.target);
  });
  u(el).on("change", function (e) {
    showLocalTime(e.target);
  });
}

function clearEmptyCompetitorRows() {
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
}

function addCompetitor(name, shortName, startTime, deviceId) {
  u(".add-competitor-btn").first().click();
  var inputs = u(u(".formset_row").last()).find("input").nodes;
  if (startTime) {
    inputs[5].value = dayjs(startTime).utc().format("YYYY-MM-DD HH:mm:ss");
    u(inputs[5]).trigger("change");
  }
  inputs[2].value = name;
  inputs[3].value = shortName;
  if (deviceId) {
    var myDeviceSelectInput = lastDeviceSelectInput;
    reqwest({
      url: window.local.apiBaseUrl + "search/device?q=" + deviceId,
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
}

function displayRoutechoicesListedOption(value, first) {
  if (value === "public") {
    u("#id_list_on_routechoices_com").parent().parent().show();
    if (!first) {
      u("#id_list_on_routechoices_com").first().checked = true;
    }
  } else {
    u("#id_list_on_routechoices_com").parent().parent().hide();
    u("#id_list_on_routechoices_com").first().checked = false;
  }
}

function onIofXMLLoaded(e) {
  var file = e.target.files[0];
  if (file) {
    var reader = new FileReader();
    reader.onload = function (evt) {
      var txt = evt.target.result;
      const parser = new DOMParser();
      const parsedXML = parser.parseFromString(txt, "text/xml");
      var isResultFile =
        parsedXML.getElementsByTagName("ResultList").length == 1;
      var isStartFile = parsedXML.getElementsByTagName("StartList").length == 1;
      if (!isResultFile && !isStartFile) {
        swal({
          title: "Error!",
          text: "Neither a start list or a result list",
          type: "error",
          confirmButtonText: "OK",
        });
        u("#iof_input").val("");
        return;
      }
      var classes = [];
      var selector = document.getElementById("iof_class_input");
      selector.innerHTML = "";
      var ii = 1;
      for (c of parsedXML.getElementsByTagName("Class")) {
        var id = ii;
        var name = c.getElementsByTagName("Name")[0].textContent;
        classes.push({ id, name });
        var opt = document.createElement("option");
        opt.value = id;
        opt.appendChild(document.createTextNode(name));
        selector.appendChild(opt);
        ii++;
      }
      u("#iof-step-1").addClass("d-none");
      u("#iof-step-2").removeClass("d-none");
      u("#iof-class-cancel-btn").on("click", function (e) {
        e.preventDefault();
        u("#iof-step-2").addClass("d-none");
        u("#iof-step-1").removeClass("d-none");
        u("#iof_input").val("");
      });
      u("#iof-class-submit-btn").off("click");
      u("#iof-class-submit-btn").on("click", function (e) {
        e.preventDefault();
        var classId = u("#iof_class_input").val();
        var suffix = isResultFile ? "Result" : "Start";

        clearEmptyCompetitorRows();
        var ii = 1;
        for (c of parsedXML.getElementsByTagName("Class" + suffix)) {
          if (ii === parseInt(classId, 10)) {
            for (p of c.getElementsByTagName("Person" + suffix)) {
              var startTime = null;
              var name = null;
              var shortName = null;
              try {
                startTime = p
                  .getElementsByTagName(suffix)[0]
                  .getElementsByTagName("StartTime")[0].textContent;
              } catch (e) {
                console.log(e);
              }
              try {
                name =
                  p
                    .getElementsByTagName("Person")[0]
                    .getElementsByTagName("Given")[0].textContent +
                  " " +
                  p
                    .getElementsByTagName("Person")[0]
                    .getElementsByTagName("Family")[0].textContent;
                shortName =
                  p
                    .getElementsByTagName("Person")[0]
                    .getElementsByTagName("Given")[0].textContent[0] +
                  "." +
                  p
                    .getElementsByTagName("Person")[0]
                    .getElementsByTagName("Family")[0].textContent;
              } catch (e) {
                console.log(e);
              }
              if (name) {
                addCompetitor(name, shortName, startTime);
              }
            }
            u(".add-competitor-btn").first().click();
          }
          ii++;
        }
        u("#iof-step-2").addClass("d-none");
        u("#iof-step-1").removeClass("d-none");
        u("#iof_input").val("");
      });
    };
    reader.onerror = function () {
      swal({
        title: "Error!",
        text: "Could not parse this file",
        type: "error",
        confirmButtonText: "OK",
      });
    };
    reader.readAsText(file, "UTF-8");
  }
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
  }
  clearEmptyCompetitorRows();
  result.data.forEach(function (l) {
    if (l.length != 1) {
      addCompetitor(l[0], l[1], l[2], l?.[3]);
    }
  });
  u(".add-competitor-btn").first().click();
}

function showLocalTime(el) {
  var val = u(el).val();
  if (val) {
    var local = dayjs(val).utc(true).local().format("YYYY-MM-DD HH:mm:ss");
    local += local === "Invalid Date" ? "" : " Local time";
    u(el).parent().find(".local_time").text(local);
  } else {
    u(el).parent().find(".local_time").html("&ZeroWidthSpace;");
  }
}

(function () {
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

  var newSlug = u("#id_name").val() == "";
  var slugEdited = false;
  makeFieldRandomizable("#id_slug");
  u("#id_name").on("keyup", function (e) {
    if (!slugEdited) {
      var value = e.target.value;
      var slug = slugify(value, {
        strict: true,
        replacement: "-",
        trim: true,
      });
      u("#id_slug").val(slug.toLowerCase());
    }
  });
  u("#id_slug").on("blur", function (e) {
    slugEdited = e.target.value !== "";
  });
  if (newSlug) {
    u("#id_slug").val("");
  } else {
    slugEdited = true;
  }

  new TomSelect("#id_event_set", {
    allowEmptyOption: true,
    render: {
      option_create: function (data, escape) {
        return (
          '<div class="create">Create <strong>' +
          escape(data.input) +
          "</strong>&hellip;</div>"
        );
      },
    },
    create: function (input, callback) {
      reqwest({
        url: window.local.apiBaseUrl + "event-set",
        method: "post",
        data: {
          club_slug: window.local.clubSlug,
          name: input,
        },
        type: "json",
        withCredentials: true,
        crossOrigin: true,
        headers: {
          "X-CSRFToken": window.local.csrfToken,
        },
        success: function (res) {
          return callback(res);
        },
        error: function () {
          return callback();
        },
      });
    },
  });

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
    new tempusDominus.TempusDominus(el, options);
  });
  u('label[for$="-DELETE"]').parent(".form-group").hide();
  $(".formset_row").formset({
    addText: '<i class="fa-solid fa-circle-plus"></i> Add Competitor',
    addCssClass: "btn btn-info add-competitor-btn",
    deleteCssClass: "btn btn-danger delete-row",
    deleteText: '<i class="fa-solid fa-xmark"></i>',
    prefix: "competitors",
    added: onAddedCompetitorRow,
  });
  $(".extra_map_formset_row").formset({
    addText: '<i class="fa-solid fa-circle-plus"></i> Add Map',
    addCssClass: "btn btn-info add-map-btn",
    deleteCssClass: "btn btn-danger delete-row",
    deleteText: '<i class="fa-solid fa-xmark"></i>',
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
    ".competitor-table .datetimepicker"
  ).filter(function (el) {
    return originalEventStart !== "" && u(el).val() == originalEventStart;
  }).nodes;
  u("#csv_input").on("change", function (e) {
    Papa.parse(e.target.files[0], { complete: onCsvParsed });
  });

  u("#iof_input").on("change", onIofXMLLoaded);
  u(".competitor-table .datetimepicker").each(makeTimeFieldClearable);
  u(".datetimepicker").each(function (el) {
    u(el).attr("autocomplete", "off");
    makeFieldNowable(el);
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
    u(el).on("change", function (e) {
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

  var tailLenFormDiv = u("<div/>").addClass("row", "g-1");

  var hourInput = u("<input/>")
    .addClass("d-inline-block")
    .addClass("form-control", "tailLengthControl")
    .css({ width: "85px" })
    .attr({
      type: "number",
      min: "0",
      max: "9999",
      name: "hours",
    })
    .val(Math.floor(tailLength / 3600));

  var hourDiv = u("<div/>")
    .addClass("col-auto")
    .append(hourInput)
    .append("<span> : </span>");

  var minuteInput = u("<input/>")
    .addClass("d-inline-block")
    .addClass("form-control", "tailLengthControl")
    .css({ width: "65px" })
    .attr({
      type: "number",
      min: "0",
      max: "59",
      name: "minutes",
    })
    .val(Math.floor(tailLength / 60) % 60);

  var minuteDiv = u("<div/>")
    .addClass("col-auto")
    .append(minuteInput)
    .append("<span> : </span>");

  var secondInput = u("<input/>")
    .addClass("d-inline-block")
    .addClass("form-control", "tailLengthControl")
    .css({ width: "65px" })
    .attr({
      type: "number",
      min: "0",
      max: "59",
      name: "seconds",
    })
    .val(tailLength % 60);

  var secondDiv = u("<div/>").addClass("col-auto").append(secondInput);

  tailLenFormDiv.append(hourDiv).append(minuteDiv).append(secondDiv);

  u("#id_tail_length").after(tailLenFormDiv);
  u(tailLenFormDiv)
    .find(".tailLengthControl")
    .on("input", function (e) {
      var commonDiv = u(e.target).parent().parent();
      var hourInput = commonDiv.find('input[name="hours"]');
      var minInput = commonDiv.find('input[name="minutes"]');
      var secInput = commonDiv.find('input[name="seconds"]');
      var h = parseInt(hourInput.val() || 0);
      var m = parseInt(minInput.val() || 0);
      var s = parseInt(secInput.val() || 0);
      var v = 3600 * h + 60 * m + s;
      if (isNaN(v)) {
        return;
      }
      var tailLength = Math.max(0, v);
      u("#id_tail_length").val(tailLength);
      hourInput.val(Math.floor(tailLength / 3600));
      minInput.val(Math.floor((tailLength / 60) % 60));
      secInput.val(Math.floor(tailLength % 60));
    });

  u("#id_backdrop_map").parent().before("<hr/><h3>Maps</h3>");
  u("#id_privacy").on("change", function (e) {
    displayRoutechoicesListedOption(e.target.value, false);
  });
  displayRoutechoicesListedOption(u("#id_privacy").val(), true);

  u("form").on("submit", function (e) {
    u("#submit-btn").attr({ disabled: true });
    u("button[name='save_continue']").addClass("disabled");
    u(e.submitter)
      .find("i")
      .removeClass("fa-floppy-disk")
      .addClass("fa-spinner fa-spin");
  });
})();
