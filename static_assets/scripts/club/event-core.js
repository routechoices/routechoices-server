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
  es: "Espa&ntilde;ol",
  fr: "Fran&ccedil;ais",
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
      '<div class="m-0 py-0 px-2"><span style="background-color:red;color: white;" class="px-1 rounded">' +
      banana.i18n("live-mode") +
      "</span></div>" +
      '<div class="m-0 py-0 px-2" style="font-size:0.7rem;color: #09F;text-shadow: -1px -1px 0 #fff,-1px 0px 0 #fff,-1px 1px 0 #fff,0px -1px 0 #fff,0px 0px 0 #fff,0px 1px 0 #fff,1px -1px 0 #fff,1px 0px 0 #fff,1px 1px 0 #fff"><span>' +
      '<svg width="30" height="12" viewBox="0 0 11.492 5.042" xmlns="http://www.w3.org/2000/svg"><g color="#000"><path d="M3.7676 2.5293c-.78376.049064-1.7114.36924-2.8574 1.0605a.321.321 0 0 0-.10938.44141l.44727.74023a.321.321 0 0 0 .44141.10938c1.3557-.81779 2.1103-.90852 2.5586-.83008.44858.078498.73271.35208 1.1738.70703 1.1915.95876 3.3161 1.1119 4.9746-.17383a.321.321 0 0 0 .05664-.45117l-.5293-.68359a.321.321 0 0 0-.45117-.056641c-.54016.41875-1.1798.58051-1.7617.57617s-1.102-.19025-1.3438-.38477c-.35274-.28384-.93328-.85518-1.8613-1.0176-.23196-.040591-.47703-.053464-.73828-.037109z" fill="#fff" style="-inkscape-stroke:none" transform="translate(.97106 -1.1383)"/><g fill="#fff" stroke-width=".82336"><path d="M1.498 1.7637A1.8566 1.8923 0 0 0-.3594 3.6563 1.8566 1.8923 0 0 0 1.498 5.5469a1.8566 1.8923 0 0 0 1.8555-1.8906A1.8566 1.8923 0 0 0 1.498 1.7637z" style="-inkscape-stroke:none" transform="matrix(1.2143 0 0 1.2148 .65693 -1.91948)"/><path d="M3.3545 3.6554a1.8566 1.8923 0 0 1-1.8566 1.8923A1.8566 1.8923 0 0 1-.3587 3.6554a1.8566 1.8923 0 0 1 1.8566-1.8923 1.8566 1.8923 0 0 1 1.8566 1.8923z" style="-inkscape-stroke:none" transform="matrix(1.2143 0 0 1.2148 .65693 -1.91948)"/><path d="M1.498 1.5801c-1.1259 0-2.0391.93432-2.0391 2.0762 0 1.1419.91315 2.0742 2.0391 2.0742 1.1259 0 2.0391-.93236 2.0391-2.0742S2.62395 1.5801 1.498 1.5801zm0 .36523c.92486 0 1.6738.76263 1.6738 1.7109s-.74897 1.709-1.6738 1.709c-.92486 0-1.6738-.76067-1.6738-1.709s.74897-1.7109 1.6738-1.7109z" style="-inkscape-stroke:none" transform="matrix(1.2143 0 0 1.2148 .65693 -1.91948)"/></g><path d="M4.4512 2.8828c-.82561-.14448-1.884.083019-3.375.98242l.44727.74023c1.3921-.83976 2.2292-.96736 2.7793-.87109s.89279.42943 1.3203.77344c1.0549.84885 3.0344 1.0175 4.5762-.17773l-.5293-.68359c-1.2109.93876-2.8509.71292-3.5039.1875-.3772-.30352-.88924-.8067-1.7148-.95117z" fill="#09F" style="-inkscape-stroke:none" transform="translate(.97106 -1.1383)"/><path d="M2.46906.6254A1.8566 1.8923 0 0 0 .61166 2.518a1.8566 1.8923 0 0 0 1.8574 1.8906 1.8566 1.8923 0 0 0 1.8555-1.8906A1.8566 1.8923 0 0 0 2.46906.6254z" fill="#09F"/><path d="M4.32556 2.5171a1.8566 1.8923 0 0 1-1.8566 1.8923 1.8566 1.8923 0 0 1-1.8566-1.8923A1.8566 1.8923 0 0 1 2.46896.6248a1.8566 1.8923 0 0 1 1.8566 1.8923z" fill="#09F"/><path d="M2.46906.4418c-1.1259 0-2.0391.93432-2.0391 2.0762 0 1.1419.91315 2.0742 2.0391 2.0742 1.1259 0 2.0391-.93236 2.0391-2.0742S3.59501.4418 2.46906.4418zm0 .36523c.92486 0 1.6738.76263 1.6738 1.7109s-.74897 1.709-1.6738 1.709c-.92486 0-1.6738-.76067-1.6738-1.709s.74897-1.7109 1.6738-1.7109z"/></g></svg>' +
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
      '<div class="m-0 py-0 px-2"><span class="px-1 rounded" style="background-color: #666;color: white">' +
      banana.i18n("replay-mode") +
      "</span></div>" +
      '<div id="big-clock" class="py-0 px-2" style="font-size:1rem;color: #000;text-shadow: -1px -1px 0 #fff,-1px 0px 0 #fff,-1px 1px 0 #fff,0px -1px 0 #fff,0px 0px 0 #fff,0px 1px 0 #fff,1px -1px 0 #fff,1px 0px 0 #fff,1px 1px 0 #fff""></div>' +
      '<div class="m-0 py-0 px-2" style="font-size:0.7rem;color: #09F;text-shadow: -1px -1px 0 #fff,-1px 0px 0 #fff,-1px 1px 0 #fff,0px -1px 0 #fff,0px 0px 0 #fff,0px 1px 0 #fff,1px -1px 0 #fff,1px 0px 0 #fff,1px 1px 0 #fff"><span>' +
      '<svg width="30" height="12" viewBox="0 0 11.492 5.042" xmlns="http://www.w3.org/2000/svg"><g color="#000"><path d="M3.7676 2.5293c-.78376.049064-1.7114.36924-2.8574 1.0605a.321.321 0 0 0-.10938.44141l.44727.74023a.321.321 0 0 0 .44141.10938c1.3557-.81779 2.1103-.90852 2.5586-.83008.44858.078498.73271.35208 1.1738.70703 1.1915.95876 3.3161 1.1119 4.9746-.17383a.321.321 0 0 0 .05664-.45117l-.5293-.68359a.321.321 0 0 0-.45117-.056641c-.54016.41875-1.1798.58051-1.7617.57617s-1.102-.19025-1.3438-.38477c-.35274-.28384-.93328-.85518-1.8613-1.0176-.23196-.040591-.47703-.053464-.73828-.037109z" fill="#fff" style="-inkscape-stroke:none" transform="translate(.97106 -1.1383)"/><g fill="#fff" stroke-width=".82336"><path d="M1.498 1.7637A1.8566 1.8923 0 0 0-.3594 3.6563 1.8566 1.8923 0 0 0 1.498 5.5469a1.8566 1.8923 0 0 0 1.8555-1.8906A1.8566 1.8923 0 0 0 1.498 1.7637z" style="-inkscape-stroke:none" transform="matrix(1.2143 0 0 1.2148 .65693 -1.91948)"/><path d="M3.3545 3.6554a1.8566 1.8923 0 0 1-1.8566 1.8923A1.8566 1.8923 0 0 1-.3587 3.6554a1.8566 1.8923 0 0 1 1.8566-1.8923 1.8566 1.8923 0 0 1 1.8566 1.8923z" style="-inkscape-stroke:none" transform="matrix(1.2143 0 0 1.2148 .65693 -1.91948)"/><path d="M1.498 1.5801c-1.1259 0-2.0391.93432-2.0391 2.0762 0 1.1419.91315 2.0742 2.0391 2.0742 1.1259 0 2.0391-.93236 2.0391-2.0742S2.62395 1.5801 1.498 1.5801zm0 .36523c.92486 0 1.6738.76263 1.6738 1.7109s-.74897 1.709-1.6738 1.709c-.92486 0-1.6738-.76067-1.6738-1.709s.74897-1.7109 1.6738-1.7109z" style="-inkscape-stroke:none" transform="matrix(1.2143 0 0 1.2148 .65693 -1.91948)"/></g><path d="M4.4512 2.8828c-.82561-.14448-1.884.083019-3.375.98242l.44727.74023c1.3921-.83976 2.2292-.96736 2.7793-.87109s.89279.42943 1.3203.77344c1.0549.84885 3.0344 1.0175 4.5762-.17773l-.5293-.68359c-1.2109.93876-2.8509.71292-3.5039.1875-.3772-.30352-.88924-.8067-1.7148-.95117z" fill="#09F" style="-inkscape-stroke:none" transform="translate(.97106 -1.1383)"/><path d="M2.46906.6254A1.8566 1.8923 0 0 0 .61166 2.518a1.8566 1.8923 0 0 0 1.8574 1.8906 1.8566 1.8923 0 0 0 1.8555-1.8906A1.8566 1.8923 0 0 0 2.46906.6254z" fill="#09F"/><path d="M4.32556 2.5171a1.8566 1.8923 0 0 1-1.8566 1.8923 1.8566 1.8923 0 0 1-1.8566-1.8923A1.8566 1.8923 0 0 1 2.46896.6248a1.8566 1.8923 0 0 1 1.8566 1.8923z" fill="#09F"/><path d="M2.46906.4418c-1.1259 0-2.0391.93432-2.0391 2.0762 0 1.1419.91315 2.0742 2.0391 2.0742 1.1259 0 2.0391-.93236 2.0391-2.0742S3.59501.4418 2.46906.4418zm0 .36523c.92486 0 1.6738.76263 1.6738 1.7109s-.74897 1.709-1.6738 1.709c-.92486 0-1.6738-.76067-1.6738-1.709s.74897-1.7109 1.6738-1.7109z"/></g></svg>' +
      '</span> <span id="tail-length-display" style="text-transform: none;">' +
      printTime(myEvent?.getTailLength()) +
      "</span></div>";
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
        '<h6><span style="color: ' +
        k.color +
        '">&#11044;</span> ' +
        banana.i18n("group") +
        " " +
        alphabetizeNumber(i) +
        "</h6>";
      k.parts.forEach(function (ci) {
        out +=
          '<div class="text-nowrap" style="clear:both;width:200px;height:1em"><span class="text-nowrap overflow-hidden float-start d-inline-block text-truncate" style="width:195px;"><span style="color: ' +
          c[ci].color +
          '">&#11044;</span> ' +
          u("<span/>").text(c[ci].name).html() +
          "</span></div>";
      });
    });
    if (out === "") {
      out = "<h6>" + banana.i18n("no-group") + "</h6>";
    }
    var testOut = u("<div>").html(out);
    if (el.html() !== testOut.html()) {
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

function intersectRatio(a, b, c, d) {
  denominator = (d.y - c.y) * (b.x - a.x) - (d.x - c.x) * (b.y - a.y);
  return ((d.x - c.x) * (a.y - c.y) - (d.y - c.y) * (a.x - c.x)) / denominator;
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
      rightSide ? 0 : 20,
    ],
  });
  return runnerIcon;
}

function getSplitLineMarker(name, color = "purple") {
  var iconStyle = `color: ${color};opacity: 0.75;`;
  var iconHtml = `<span style="${iconStyle}">${u("<span/>")
    .text(name)
    .text()}</span>`;
  var iconClass = "runner-icon runner-icon-dark";
  var icon = L.divIcon({
    className: iconClass,
    html: iconHtml,
    iconAnchor: [10, 0],
  });
  return icon;
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
  return fetch(`${langFile}?v=2024062100`)
    .then((response) => response.json())
    .then((messages) => {
      banana.load(messages, banana.locale);
    });
}
