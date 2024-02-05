var COLORS = [
  "#e6194B",
  "#3cb44b",
  "#4363d8",
  "#f58231",
  "#911eb4",
  "#42d4f4",
  "#f032e6",
  "#bfef45",
  "#ffe119",
  "#800000",
  "#469990",
  "#9A6324",
  "#aaffc3",
  "#808000",
  "#000075",
  "#a9a9a9",
  "#000000",
];
var supportedLanguages = {
  en: "English",
  es: "Español",
  fr: "Français",
  nl: "Nederlands",
  pl: "Polski",
  fi: "Suomi",
  sv: "Svenska",
};

var myEvent = null;
var banana = null;
var locale = null;

var printTime = function (t) {
  var prependZero = function (x) {
    return ("0" + x).slice(-2);
  };
  t = Math.round(t);
  var h = Math.floor(t / 3600),
    m = Math.floor((t % 3600) / 60),
    s = t % 60;
  if (h === 0) {
    var text = "";
    if (m == 0) {
      return s + "s";
    }
    text = m + "min";
    if (s === 0) {
      return text;
    }
    return text + prependZero(s) + "s";
  }
  var text = h + "h";
  if (m === 0 && s === 0) {
    return text;
  }
  text += prependZero(m) + "min";
  if (s === 0) {
    return text;
  }
  return text + prependZero(s) + "s";
};

L.Control.EventState = L.Control.extend({
  options: {
    position: "topleft",
  },

  addHooks: function () {
    L.DomEvent.on(event, "eventname", this._doSomething, this);
  },

  removeHooks: function () {
    L.DomEvent.off(event, "eventname", this._doSomething, this);
  },

  onAdd: function (map) {
    var div = L.DomUtil.create("div");
    div.style.userSelect = "none";
    div.style["-webkit-user-select"] = "none";
    this._div = div;
    return div;
  },
  hide() {
    if (!this._div) {
      return;
    }
    this._div.style.display = "none";
  },
  setLive() {
    if (!this._div) {
      return;
    }
    this._div.innerHTML =
      '<div class="m-0 py-0 px-2 fst-italic" style="color: red;text-shadow: -1px -1px 0 #fff,-1px 0px 0 #fff,-1px 1px 0 #fff,0px -1px 0 #fff,0px 0px 0 #fff,0px 1px 0 #fff,1px -1px 0 #fff,1px 0px 0 #fff,1px 1px 0 #fff">' +
      banana.i18n("live-mode") +
      "</div>" +
      '<div class="m-0 py-0 px-2" style="font-size:1rem;color: #09F;text-shadow: -1px -1px 0 #fff,-1px 0px 0 #fff,-1px 1px 0 #fff,0px -1px 0 #fff,0px 0px 0 #fff,0px 1px 0 #fff,1px -1px 0 #fff,1px 0px 0 #fff,1px 1px 0 #fff"><span>' +
      banana.i18n("tails") +
      '</span> <span id="tail-length-display" style="text-transform: none;">' +
      printTime(myEvent?.getTailLength()) +
      "</span></div>" +
      '<div id="big-clock" class="py-0 px-2" style="font-size:1rem;color: #000;text-shadow: -1px -1px 0 #fff,-1px 0px 0 #fff,-1px 1px 0 #fff,0px -1px 0 #fff,0px 0px 0 #fff,0px 1px 0 #fff,1px -1px 0 #fff,1px 0px 0 #fff,1px 1px 0 #fff"></div>';
    u(this._div).css({
      display: "block",
      fontSize: "20px",
      color: "#fff",
      padding: "0",
      fontWeight: "bold",
      textTransform: "uppercase",
      marginLeft: "0px",
    });
  },
  setReplay() {
    this._div.innerHTML =
      '<div class="m-0 py-0 px-2" style="color: #666;text-shadow: -1px -1px 0 #fff,-1px 0px 0 #fff,-1px 1px 0 #fff,0px -1px 0 #fff,0px 0px 0 #fff,0px 1px 0 #fff,1px -1px 0 #fff,1px 0px 0 #fff,1px 1px 0 #fff">' +
      banana.i18n("replay-mode") +
      "</div>" +
      '<div class="m-0 py-0 px-2" style="font-size:1rem;color: #09F;text-shadow: -1px -1px 0 #fff,-1px 0px 0 #fff,-1px 1px 0 #fff,0px -1px 0 #fff,0px 0px 0 #fff,0px 1px 0 #fff,1px -1px 0 #fff,1px 0px 0 #fff,1px 1px 0 #fff"><span>' +
      banana.i18n("tails") +
      '</span> <span id="tail-length-display" style="text-transform: none;">' +
      printTime(myEvent?.getTailLength()) +
      "</span></div>" +
      '<div id="big-clock" class="py-0 px-2" style="font-size:1rem;color: #000;text-shadow: -1px -1px 0 #fff,-1px 0px 0 #fff,-1px 1px 0 #fff,0px -1px 0 #fff,0px 0px 0 #fff,0px 1px 0 #fff,1px -1px 0 #fff,1px 0px 0 #fff,1px 1px 0 #fff""></div>';
    u(this._div).css({
      display: "block",
      fontSize: "20px",
      color: "#fff",
      padding: "0",
      fontWeight: "bold",
      textTransform: "uppercase",
      marginLeft: "0px",
    });
  },
  onRemove: function (map) {
    // Nothing to do here
  },
});

L.control.eventState = function (opts) {
  return new L.Control.EventState(opts);
};

L.Control.Ranking = L.Control.extend({
  onAdd: function (map) {
    var back = L.DomUtil.create(
      "div",
      "leaflet-bar leaflet-control leaflet-control-ranking"
    );
    back.setAttribute("data-bs-theme", "light");
    u(back).append('<div class="result-name-list"/>');
    back.style.width = "205px";
    back.style.background = "white";
    back.style.color = "black";
    back.style.padding = "5px";
    back.style.top = "0px";
    back.style.right = "0px";
    back.style["max-height"] = "195px";
    back.style["overflow-y"] = "auto";
    back.style["overflow-x"] = "hidden";
    back.style["z-index"] = 10000;
    back.style["font-size"] = "12px";
    L.DomEvent.on(back, "mousewheel", L.DomEvent.stopPropagation);
    L.DomEvent.on(back, "touchstart", L.DomEvent.stopPropagation);
    L.DomEvent.on(back, "click", L.DomEvent.stopPropagation);
    L.DomEvent.on(back, "dblclick", L.DomEvent.stopPropagation);
    return back;
  },

  setValues: function (ranking) {
    var el = u(".leaflet-control-ranking").find(".result-name-list");
    if (
      u(".leaflet-control-ranking").find(".result-list-title").nodes.length ===
      0
    ) {
      u(".leaflet-control-ranking").prepend(
        '<div class="result-list-title">' +
          '<h6><i class="fa-solid fa-trophy"></i> ' +
          banana.i18n("ranking") +
          "</h6><label>" +
          banana.i18n("crossing-count") +
          '</label><input type="number" min="1" id="crossing-time" step="1" value="1" class="d-block cross-count form-control" style="font-size: 0.7rem;width: 61px">' +
          "</div>"
      );
    }
    var innerOut = u('<div class="result-name-list"/>');
    if (ranking.length > 0) {
      ranking.sort(function (a, b) {
        return (
          myEvent.getRelativeTime(a.time) - myEvent.getRelativeTime(b.time)
        );
      });
    }
    ranking.forEach(function (c, i) {
      innerOut.append(
        '<div class="text-nowrap overflow-hidden text-truncate" style="clear: both; width: 200px;"><span class="text-nowrap d-inline-block float-start overflow-hidden text-truncate" style="width: 135px;">' +
          (i + 1) +
          ' <span style="color: ' +
          c.competitor.color +
          '">⬤</span> ' +
          u("<span/>").text(c.competitor.name).html() +
          '</span><span class="text-nowrap overflow-hidden d-inline-block float-end" style="width: 55px; font-feature-settings: tnum; font-variant-numeric: tabular-nums lining-nums; margin-right: 10px;" title="' +
          myEvent.getProgressBarText(c.time) +
          '">' +
          myEvent.getProgressBarText(c.time) +
          "</span></div>"
      );
    });
    if (innerOut.html() === "") {
      innerOut.append("<div>-</div>");
    }
    if (el.html() !== innerOut.html()) {
      el.html(innerOut.html());
    }
  },

  onRemove: function (map) {
    u(".leaflet-control-ranking").remove();
    u(".tmp").remove();
  },
});

L.control.ranking = function (opts) {
  return new L.Control.Ranking(opts);
};

L.Control.Grouping = L.Control.extend({
  onAdd: function (map) {
    var back = L.DomUtil.create(
      "div",
      "leaflet-bar leaflet-control leaflet-control-grouping"
    );
    back.setAttribute("data-bs-theme", "light");
    back.style.width = "205px";
    back.style.background = "white";
    back.style.color = "black";
    back.style.padding = "5px";
    back.style.top = "0px";
    back.style.right = "0px";
    back.style["max-height"] = "195px";
    back.style["overflow-y"] = "auto";
    back.style["overflow-x"] = "hidden";
    back.style["z-index"] = 10000;
    back.style["font-size"] = "12px";
    L.DomEvent.on(back, "mousewheel", L.DomEvent.stopPropagation);
    L.DomEvent.on(back, "touchstart", L.DomEvent.stopPropagation);
    return back;
  },

  setValues: function (c, cl) {
    var el = u(".leaflet-control-grouping");
    var out = "";
    cl.forEach(function (k, i) {
      if (i !== 0) {
        out += "<br>";
      }
      out +=
        "<h6>" + banana.i18n("group") + " " + alphabetizeNumber(i) + "</h6>";
      k.parts.forEach(function (ci) {
        out +=
          '<div class="text-nowrap" style="clear:both;width:200px;height:1em"><span class="text-nowrap overflow-hidden float-start d-inline-block text-truncate" style="width:195px;"><span style="color: ' +
          c[ci].color +
          '">⬤</span> ' +
          u("<span/>").text(c[ci].name).html() +
          "</span></div>";
      });
    });
    if (out === "") {
      out = "<h6>" + banana.i18n("no-group") + "</h6>";
    }
    if (el.html() !== out) {
      el.html(out);
    }
  },

  onRemove: function (map) {
    u(".leaflet-control-grouping").remove();
    u(".tmp2").remove();
  },
});

L.control.grouping = function (opts) {
  return new L.Control.Grouping(opts);
};

function getLangIfSupported(code) {
  return Object.keys(supportedLanguages).includes(code) ? code : null;
}

function getColor(i) {
  return COLORS[i % COLORS.length];
}

function getContrastYIQ(hexcolor) {
  hexcolor = hexcolor.replace("#", "");
  var hexSize = 0x10;
  var r = parseInt(hexcolor.substr(0, 2), hexSize);
  var g = parseInt(hexcolor.substr(2, 2), hexSize);
  var b = parseInt(hexcolor.substr(4, 2), hexSize);
  var yiq = (r * 299 + g * 587 + b * 114) / 1000;
  return yiq <= 168;
}

function getRunnerIcon(color, faded = false, focused = false) {
  var iconSize = 16;
  var liveColor = tinycolor(color).setAlpha(faded ? 0.4 : 0.75);
  var svgRect = `<svg viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg"><circle fill="${liveColor.toRgbString()}" stroke="black" stroke-width="${
    focused ? 3 : 1
  }px" cx="8" cy="8" r="6"/></svg>`;
  var runnerIcon = L.icon({
    iconUrl: encodeURI("data:image/svg+xml," + svgRect),
    iconSize: [iconSize, iconSize],
    shadowSize: [iconSize, iconSize],
    iconAnchor: [iconSize / 2, iconSize / 2],
    shadowAnchor: [0, 0],
    popupAnchor: [0, 0],
    className: focused ? "icon-focused" : "",
  });
  return runnerIcon;
}

function getRunnerNameMarker(
  name,
  color,
  isDark,
  rightSide,
  faded = false,
  focused = false
) {
  var iconStyle = `color: ${color};opacity: ${faded ? 0.4 : 0.75};${
    focused ? `padding-bottom: 0px;border-bottom: 4px solid ${color};` : ""
  }`;
  var iconHtml = `<span style="${iconStyle}">${u("<span/>")
    .text(name)
    .text()}</span>`;
  var iconClass = `runner-icon runner-icon-${isDark ? "dark" : "light"}${
    needFlagsEmojiPolyfill ? " flags-polyfill" : ""
  }${focused ? " icon-focused" : ""}`;

  // mesure tagname width
  var tmpIconClass = `${iconClass} leaflet-marker-icon leaflet-zoom-animated leaflet-interactive`;
  var nameTagEl = document.createElement("div");
  nameTagEl.className = tmpIconClass;
  nameTagEl.innerHTML = iconHtml;
  var mapEl = document.getElementById("map");
  mapEl.appendChild(nameTagEl);
  var nameTagWidth = nameTagEl.childNodes[0].getBoundingClientRect().width;
  mapEl.removeChild(nameTagEl);

  var runnerIcon = L.divIcon({
    className: iconClass,
    html: iconHtml,
    iconAnchor: [
      rightSide ? nameTagWidth + (focused ? 10 : 0) : focused ? -10 : 0,
      rightSide ? 0 : 30,
    ],
  });
  return runnerIcon;
}

function alphabetizeNumber(integer) {
  return Number(integer)
    .toString(26)
    .split("")
    .map((c) =>
      (c.charCodeAt() > 96
        ? String.fromCharCode(c.charCodeAt() + 10)
        : String.fromCharCode(97 + parseInt(c))
      ).toUpperCase()
    )
    .join("");
}

function batteryIconName(perc) {
  if (perc === null) return "half";
  var level = Math.min(4, Math.round((perc - 5) / 20));
  return ["empty", "quarter", "half", "three-quarters", "full"][level];
}

function toggleCompetitorFullRoute(competitor) {
  if (!competitor.isShown) {
    return;
  }
  if (competitor.displayFullRoute) {
    competitor.displayFullRoute = null;
    competitor.sidebarCard
      ?.find(".full-route-icon")
      .attr({ fill: "var(--bs-body-color)" });
  } else {
    competitor.displayFullRoute = true;
    competitor.sidebarCard?.find(".full-route-icon").attr({ fill: "#20c997" });
  }
}

function sortingFunction(a, b) {
  return a - b;
}

function updateText() {
  banana.setLocale(locale);
  var langFile = `${window.local.staticRoot}i18n/club/event/${locale}.json`;
  return fetch(`${langFile}?v=2024020500`)
    .then((response) => response.json())
    .then((messages) => {
      banana.load(messages, banana.locale);
    });
}
