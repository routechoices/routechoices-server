var events = [];
var browserLanguage = navigator.language.slice(0, 2);
var supportedLanguages = {
  en: "English",
  es: "Español",
  fr: "Français",
  fi: "Suomi",
  nl: "Nederlands",
  pl: "Polski",
  sv: "Svensk",
};
var locale =
  window.localStorage.getItem("lang") ||
  (Object.keys(supportedLanguages).includes(browserLanguage)
    ? browserLanguage
    : "en");
const banana = new Banana();

function updateText() {
  banana.setLocale(locale);
  var langFile =
    window.local.staticRoot +
    "i18n/site/registration/" +
    locale +
    ".json?v=2024020300";
  return fetch(langFile)
    .then((response) => response.json())
    .then((messages) => {
      banana.load(messages, banana.locale);
    });
}

window.onload = function () {
  updateText().then(function () {
    document.getElementById("name-label").innerHTML = banana.i18n("name");
    document.getElementById("sname-label").innerHTML =
      banana.i18n("short-name");
    document.getElementById("dev-id-label").innerHTML = banana.i18n("dev-id");
    document.getElementById("save-btn").value = banana.i18n("save");
    document.getElementById("register-btn").value =
      banana.i18n("register-this");
    document.getElementById("event-label").innerHTML = banana.i18n("event");
    document.getElementById("no-events").innerHTML = banana.i18n("no-events");
    document.getElementById("registered").innerHTML = banana.i18n("registered");
    document.getElementById("registration-info").innerHTML =
      banana.i18n("registration-info");
    document.getElementById("register-title").innerHTML =
      banana.i18n("register");
    [...document.getElementsByClassName("settings-text")].map(function (el) {
      el.innerHTML = banana.i18n("settings");
    });
    [...document.getElementsByClassName("refresh-text")].map(function (el) {
      el.innerHTML = banana.i18n("refresh");
    });
    var userInfo = window.localStorage.getItem("userInfo");
    var myUrl = new URL(window.location.href.replace(/#/g, "?"));
    var devid = myUrl.searchParams.get("device_id");
    document.getElementById("devid").value = devid || "";
    if (userInfo) {
      try {
        userInfo = JSON.parse(userInfo);
        document.getElementById("name").value = userInfo.name;
        document.getElementById("sname").value = userInfo.short_name;
        document.getElementById("devid").value = devid || userInfo.devid || "";
        document.getElementById("p1").classList.add("d-none");
        document.getElementById("user-summary").textContent =
          userInfo.name +
          " (" +
          userInfo.short_name +
          ")" +
          " - " +
          userInfo.devid;
        document.getElementById("p0").classList.remove("d-none");
        fetchEvents();
      } catch (e) {
        document.getElementById("p2").classList.add("d-none");
        document.getElementById("p1").classList.remove("d-none");
        document.getElementById("p0").classList.add("d-none");
      }
    } else {
      document.getElementById("p2").classList.add("d-none");
      document.getElementById("p1").classList.remove("d-none");
      document.getElementById("p0").classList.add("d-none");
    }
  });
  document.getElementById("events").addEventListener("change", onEventSelect);
};
document.getElementById("form1").onsubmit = async function (ev) {
  ev.preventDefault();
  var deviceIdRaw = document.getElementById("devid").value;
  var resp = await fetch(window.local.apiRoot + "device/" + deviceIdRaw, {
    method: "GET",
    credentials: "omit",
    headers: {
      "Content-Type": "application/json",
    },
  });
  var content = await resp.json();
  if (content.error) {
    swal(banana.i18n("no-device-id"));
    return;
  }
  userInfo = {};
  userInfo.name = document.getElementById("name").value;
  userInfo.short_name = document.getElementById("sname").value;
  userInfo.devid = document.getElementById("devid").value;
  window.localStorage.setItem("userInfo", JSON.stringify(userInfo));
  document.getElementById("p1").classList.add("d-none");
  document.getElementById("user-summary").textContent =
    userInfo.name + " (" + userInfo.short_name + ")" + " - " + userInfo.devid;
  document.getElementById("p0").classList.remove("d-none");
  fetchEvents();
};
document.getElementById("form2").onsubmit = function (ev) {
  ev.preventDefault();
  data = {};
  data.name = document.getElementById("name").value;
  data.short_name = document.getElementById("sname").value;
  data.device_id = document.getElementById("devid").value;
  ev_id = document.getElementById("events").value;
  if (!ev_id) {
    return;
  }
  fetch(
    window.local.apiRoot + "events/" + ev_id + "/register/?lang=" + locale,
    {
      method: "POST",
      credentials: "omit",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(data),
    }
  )
    .then(function (r) {
      return r.json();
    })
    .then(function (data) {
      if (!data.id) {
        if (data instanceof Array) {
          swal(data.join("\r\n"));
        } else {
          swal(banana.i18n("error"));
        }
        return;
      }
      document.getElementById("p2").classList.add("d-none");
      document.getElementById("p4").classList.remove("d-none");
    })
    .catch(function (e) {
      swal(banana.i18n("error"));
    });
};
Array.from(document.getElementsByClassName("user-setting-btn")).map(function (
  el
) {
  el.addEventListener("click", function (e) {
    document.getElementById("p2").classList.add("d-none");
    document.getElementById("p3").classList.add("d-none");
    document.getElementById("p4").classList.add("d-none");
    document.getElementById("p0").classList.add("d-none");
    document.getElementById("p1").classList.remove("d-none");
  });
});
Array.from(document.getElementsByClassName("refresh-btn")).map(function (el) {
  el.addEventListener("click", function (e) {
    window.location.reload();
  });
});
function onEventSelect() {
  var select = document.getElementById("events");
  var value = select.options[select.selectedIndex].value;
  if (!value) {
    document.getElementById("warningA").classList.add("d-none");
    document.getElementById("warningB").classList.add("d-none");
    document.getElementById("register-btn").setAttribute("disabled", true);
    return;
  }
  document.getElementById("register-btn").removeAttribute("disabled");
  e = events.find(function (ev) {
    return ev.id === value;
  });
  if (dayjs(e.start_date) < dayjs()) {
    document.getElementById("warningA").classList.remove("d-none");
    document.getElementById("warningB").classList.add("d-none");
  } else {
    document.getElementById("warningA").classList.add("d-none");
    document.getElementById("warningB").classList.remove("d-none");
    document.getElementById("event_start_notice").innerHTML = banana.i18n(
      "registration-info-time",
      dayjs(e.start_date).local().locale(locale).format("LLLL")
    );
  }
}
function fetchEvents() {
  fetch(window.local.apiRoot + "events", { method: "GET" })
    .then(function (r) {
      return r.json();
    })
    .then(function (evs) {
      events = evs
        .filter(function (e) {
          return (
            e.open_registration && (!e.end_date || dayjs(e.end_date) > dayjs())
          );
        })
        .map(function (e) {
          return {
            id: e.id,
            name: e.name + " - " + e.club,
            start_date: e.start_date,
          };
        });
      if (events.length === 0) {
        document.getElementById("p3").classList.remove("d-none");
      } else {
        document.getElementById("events").innerHTML = "";
        document.getElementById("p2").classList.remove("d-none");
        var optNull = document.createElement("option");
        optNull.setAttribute("value", "");
        optNull.appendChild(document.createTextNode("-----"));
        document.getElementById("events").appendChild(optNull);
        events.forEach(function (ev) {
          var opt = document.createElement("option");
          opt.setAttribute("value", ev.id);
          opt.appendChild(document.createTextNode(ev.name));
          document.getElementById("events").appendChild(opt);
        });
        onEventSelect({ target: { value: events[0].id } });
      }
    });
}
