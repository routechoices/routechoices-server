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
var backgroundLayer = null;
var toast = null;
var locale = null;
var map = null;
var isLiveMode = false;
var liveUrl = null;
var isLiveEvent = false;
var isRealTime = true;
var isCustomStart = false;
var competitorList = [];
var competitorRoutes = {};
var competitorBatteyLevels = {};
var routesLastFetched = -Infinity;
var eventDataLastFetch = -Infinity;
var fetchPositionInterval = 10;
var playbackRate = 8;
var playbackPaused = true;
var prevDisplayRefresh = 0;
var prevMeterDisplayRefresh = 0;
var tailLength = 60;
var isCurrentlyFetchingRoutes = false;
var currentTime = 0;
var lastDataTs = 0;
var lastNbPoints = 0;
var optionDisplayed = false;
var mapHash = "";
var mapUrl = null;
var rasterMap = null;
var searchText = null;
var prevNotice = new Date(0);
var resetMassStartContextMenuItem = null;
var setMassStartContextMenuItem = null;
var setFinishLineContextMenuItem = null;
var removeFinishLineContextMenuItem = null;
var clusters = {};
var qrUrl = null;
var finishLineCrosses = [];
var finishLinePoints = [];
var finishLinePoly = null;
var finishLineSet = false;
var rankControl = null;
var groupControl = null;
var panControl = null;
var zoomControl = null;
var rotateControl = null;
var scaleControl = null;
var locateControl = null;
var showClusters = false;
var showControls = false;
var colorModal = new bootstrap.Modal(document.getElementById("colorModal"));
var zoomOnRunners = false;
var clock = null;
var banana = null;
var sendInterval = 0;
var endEvent = null;
var startEvent = null;
var initialCompetitorDataLoaded = false;
var maxParticipantsDisplayed = 500;
var nbShown = 0;
var prevMapsJSONData = null;
var mapSelectorLayer = null;
var sidebarShown = true;
var isMapMoving = false;
var oldCrossingForNTimes = 1;
var intersectionCheckZoom = 18;
var showUserLocation = false;
var mapOpacity = 1;
var showAll = true;
var supportedLanguages = {
  en: "English",
  es: "Español",
  fr: "Français",
  nl: "Nederlands",
  fi: "Suomi",
  sv: "Svenska",
};

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

Array.prototype.findIndex =
  Array.prototype.findIndex ||
  function (callback) {
    if (this === null) {
      throw new TypeError(
        "Array.prototype.findIndex called on null or undefined"
      );
    } else if (typeof callback !== "function") {
      throw new TypeError("callback must be a function");
    }
    var list = Object(this);
    var length = list.length >>> 0;
    var thisArg = arguments[1];
    for (var i = 0; i < length; i++) {
      if (callback.call(thisArg, list[i], i, list)) {
        return i;
      }
    }
    return -1;
  };

L.Control.EventState = L.Control.extend({
  options: {
    position: "topleft",
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
      printTime(tailLength) +
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
      printTime(tailLength) +
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
    u(back).append('<div class="result-name-list"/>');
    back.style.width = "205px";
    back.style.background = "white";
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
    ranking.sort(function (a, b) {
      return getRelativeTime(a.time) - getRelativeTime(b.time);
    });
    ranking.forEach(function (c, i) {
      innerOut.append(
        '<div class="text-nowrap overflow-hidden text-truncate" style="clear: both; width: 200px;"><span class="text-nowrap d-inline-block float-start overflow-hidden text-truncate" style="width: 135px;">' +
          (i + 1) +
          ' <span style="color: ' +
          c.competitor.color +
          '">⬤</span> ' +
          u("<span/>").text(c.competitor.name).html() +
          '</span><span class="text-nowrap overflow-hidden d-inline-block float-end" style="width: 55px; font-feature-settings: tnum; font-variant-numeric: tabular-nums lining-nums; margin-right: 10px;" title="' +
          getProgressBarText(c.time) +
          '">' +
          getProgressBarText(c.time) +
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
    back.style.width = "205px";
    back.style.background = "white";
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

function onLayerChange(event) {
  map.setBearing(event.layer.data.rotation, { animate: false });
  fitInnerBounds(event.layer.options.bounds);
  rasterMap = event.layer;
  rasterMap.setOpacity(mapOpacity);
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

function onAppResize() {
  const doc = document.documentElement;
  doc.style.setProperty("--app-height", `${window.innerHeight}px`);
  doc.style.setProperty(
    "--ctrl-height",
    `${document.getElementById("ctrl-wrapper").clientHeight}px`
  );
  var width = window.innerWidth > 0 ? window.innerWidth : screen.width;
  if (
    u("#sidebar").hasClass("d-sm-block") &&
    u("#sidebar").hasClass("d-none")
  ) {
    // the sidebar hasnt beeen manually collapsed yet
    if (!u("#map").hasClass("no-sidebar") && width <= 576) {
      u("#map").addClass("no-sidebar");
      u("#permanent-sidebar .btn").removeClass("active");
    } else if (u("#map").hasClass("no-sidebar") && width > 576) {
      u("#map").removeClass("no-sidebar");
      if (optionDisplayed) {
        u("#options_show_button").addClass("active");
      } else {
        u("#runners_show_button").addClass("active");
      }
    }
  }
}

function drawFinishLine(e) {
  finishLinePoints = [];
  if (finishLinePoly) {
    map.removeLayer(finishLinePoly);
    map.removeControl(rankControl);
    finishLinePoly = null;
    finishLineSet = false;
  }
  finishLinePoints.push(e.latlng);
  map.on("click", drawFinishLineEnd);
  map.on("mousemove", drawFinishLineTmp);
}

function removeFinishLine() {
  if (finishLinePoly) {
    map.removeLayer(finishLinePoly);
    map.removeControl(rankControl);
    finishLinePoly = null;
    finishLineSet = false;
    map.contextmenu.removeItem(removeFinishLineContextMenuItem);
    removeFinishLineContextMenuItem = null;
  }
}

function drawFinishLineEnd(e) {
  if (finishLinePoly) {
    map.removeLayer(finishLinePoly);
  }
  finishLinePoints.push(e.latlng);
  finishLinePoly = L.polyline(finishLinePoints, { color: "purple" });
  map.off("click", drawFinishLineEnd);
  map.off("mousemove", drawFinishLineTmp);
  rankControl = L.control.ranking({ position: "topright" });
  map.addControl(rankControl);
  map.addLayer(finishLinePoly);
  finishLineSet = true;
  if (!removeFinishLineContextMenuItem) {
    removeFinishLineContextMenuItem = map.contextmenu.insertItem(
      {
        text: banana.i18n("remove-finish-line"),
        callback: removeFinishLine,
      },
      2
    );
  }
}

function drawFinishLineTmp(e) {
  finishLinePoints[1] = e.latlng;
  if (!finishLinePoly) {
    finishLinePoly = L.polyline(finishLinePoints, { color: "purple" });
    map.addLayer(finishLinePoly);
  } else {
    finishLinePoly.setLatLngs(finishLinePoints);
  }
}

function onStart() {
  fetchCompetitorRoutes(null, function () {
    if (isLiveEvent) {
      selectLiveMode();
    } else {
      u("#live_button").remove();
      u("#replay_button").remove();
      selectReplayMode();
    }
    u("#eventLoadingModal").remove();
    u(".main").removeClass("loading");
    u(".sidebar").removeClass("loading");
    u(".time_bar").removeClass("loading");
    u("#permanent-sidebar").removeClass("loading");
    onAppResize();
    map.invalidateSize();
  });
}

function getCompetitionStartDate(nullIfNone = false) {
  var res = +clock.now();
  var found = false;
  for (var i = 0; i < competitorList.length; i++) {
    (function (competitor) {
      var route = competitorRoutes[competitor.id];
      if (route) {
        if (res > route.getByIndex(0).timestamp) {
          res = route.getByIndex(0).timestamp;
          found = true;
        }
      }
    })(competitorList[i]);
  }
  if (nullIfNone && !found) {
    return null;
  }
  return res;
}

function getCompetitionEndDate() {
  var res = new Date(0);
  for (var i = 0; i < competitorList.length; i++) {
    (function (competitor) {
      var route = competitorRoutes[competitor.id];
      if (route) {
        var idx = route.getPositionsCount() - 1;
        res =
          res < route.getByIndex(idx).timestamp
            ? route.getByIndex(idx).timestamp
            : res;
      }
    })(competitorList[i]);
  }
  return res;
}

function getCompetitorsMaxDuration(customOffset) {
  if (customOffset === undefined) {
    customOffset = false;
  }
  var res = 0;
  for (var i = 0; i < competitorList.length; i++) {
    (function (competitor) {
      var route = competitorRoutes[competitor.id];
      if (route) {
        var idx = route.getPositionsCount() - 1;
        var dur =
          route.getByIndex(idx).timestamp -
          ((customOffset
            ? +new Date(competitor.custom_offset)
            : +new Date(competitor.start_time)) || getCompetitionStartDate());
        res = res < dur ? dur : res;
      }
    })(competitorList[i]);
  }
  return res;
}

function getCompetitorsMinCustomOffset() {
  var res = 0;
  for (var i = 0; i < competitorList.length; i++) {
    (function (competitor) {
      var route = competitorRoutes[competitor.id];
      if (route) {
        var off = competitor.custom_offset - competitor.start_time || 0;
        res = res < off ? off : res;
      }
    })(competitorList[i]);
  }
  return res;
}

function selectLiveMode(e) {
  if (e !== undefined) {
    e.preventDefault();
  }
  if (isLiveMode) {
    return;
  }
  u("#full_progress_bar").addClass("d-none");

  eventStateControl.setLive();
  if (setMassStartContextMenuItem) {
    map.contextmenu.removeItem(setMassStartContextMenuItem);
    setMassStartContextMenuItem = null;
  }
  if (resetMassStartContextMenuItem) {
    map.contextmenu.removeItem(resetMassStartContextMenuItem);
    resetMassStartContextMenuItem = null;
  }
  u(".if-live").removeClass("d-none");
  u("#live_button")
    .addClass("active")
    .addClass("fst-italic")
    .text(banana.i18n("live-mode"));
  u("#replay_button").removeClass("d-none");
  u("#real_time_button").removeClass("active");
  u("#mass_start_button").removeClass("active");
  u("#replay_mode_buttons").hide();
  u("#replay_control_buttons").hide();
  onAppResize();

  isLiveMode = true;
  isRealTime = true;
  function whileLive(ts) {
    if (
      ts - routesLastFetched > fetchPositionInterval * 1e3 &&
      !isCurrentlyFetchingRoutes
    ) {
      fetchCompetitorRoutes();
    }
    currentTime =
      +clock.now() - (fetchPositionInterval + 5 + sendInterval) * 1e3; // Delay by the fetch interval (10s) + the cache interval (5sec) + the send interval (default 5sec)
    if (ts - prevDisplayRefresh > 100) {
      var refreshMeters = ts - prevMeterDisplayRefresh > 500;
      drawCompetitors(refreshMeters);
      prevDisplayRefresh = ts;
      if (refreshMeters) {
        prevMeterDisplayRefresh = ts;
      }
    }
    var isStillLive = endEvent >= clock.now();
    if (!isStillLive) {
      u("#live_button").hide();
      u("#archived_event_button").show();
      selectReplayMode();
    }
    if (isLiveMode) {
      window.requestAnimationFrame(whileLive);
    }
  }
  window.requestAnimationFrame(whileLive);
}

function selectReplayMode(e) {
  if (e !== undefined) {
    e.preventDefault();
  }
  if (!isLiveMode && u("#replay_button").hasClass("d-none")) {
    return;
  }

  u(".if-live").addClass("d-none");
  u("#full_progress_bar").removeClass("d-none");
  u("#real_time_button").addClass("active");
  u("#mass_start_button").removeClass("active");

  eventStateControl.setReplay();
  u("#live_button")
    .removeClass("active")
    .removeClass("fst-italic")
    .text(banana.i18n("return-live-mode"));
  u("#replay_button").addClass("d-none");
  u("#replay_mode_buttons").css({ display: "" });
  u("#replay_control_buttons").css({ display: "" });
  onAppResize();

  if (!setMassStartContextMenuItem) {
    setMassStartContextMenuItem = map.contextmenu.insertItem(
      {
        text: banana.i18n("mass-start-from-here"),
        callback: onPressCustomMassStart,
      },
      2
    );
  }
  isLiveMode = false;
  playbackPaused = true;
  prevDisplayRefresh = performance.now();
  prevMeterDisplayRefresh = performance.now();
  prevShownTime = getCompetitionStartDate();
  playbackRate = 8;
  function whileReplay(ts) {
    if (
      isLiveEvent &&
      ts - routesLastFetched > fetchPositionInterval * 1e3 &&
      !isCurrentlyFetchingRoutes
    ) {
      fetchCompetitorRoutes();
    }
    var actualPlaybackRate = playbackPaused ? 0 : playbackRate;
    if (getCompetitionStartDate(true) === null) {
      currentTime = 0;
      maxCTime = 0;
    } else {
      currentTime = Math.max(
        getCompetitionStartDate(),
        prevShownTime + (ts - prevDisplayRefresh) * actualPlaybackRate
      );
      var maxCTime = getCompetitionStartDate() + getCompetitorsMaxDuration();
      if (isCustomStart) {
        maxCTime =
          getCompetitionStartDate() +
          getCompetitorsMinCustomOffset() +
          getCompetitorsMaxDuration(true);
      }
      if (isRealTime) {
        maxCTime =
          getCompetitionStartDate() +
          (Math.min(+clock.now(), getCompetitionEndDate()) -
            getCompetitionStartDate());
      }
      currentTime = Math.min(+clock.now(), currentTime, maxCTime);
      var liveTime =
        +clock.now() - (fetchPositionInterval + 5 + sendInterval) * 1e3;

      if (getCompetitionStartDate(true) !== null && currentTime > liveTime) {
        selectLiveMode();
        return;
      }
    }
    if (ts - prevDisplayRefresh > 100) {
      var refreshMeters = ts - prevMeterDisplayRefresh > 500;
      drawCompetitors(refreshMeters);
      if (refreshMeters) {
        prevMeterDisplayRefresh = ts;
      }
      prevDisplayRefresh = ts;
      prevShownTime = currentTime;
    }

    var isStillLive = isLiveEvent && endEvent >= clock.now();
    var isBackLive = !isLiveEvent && endEvent >= clock.now();
    if (!isStillLive) {
      u("#live_button").hide();
      u("#archived_event_button").show();
      isLiveEvent = false;
    }
    if (isBackLive) {
      u("#live_button").show();
      u("#archived_event_button").hide();
      isLiveEvent = true;
    }

    if (!isLiveMode) {
      window.requestAnimationFrame(whileReplay);
    }
  }
  whileReplay(performance.now());
}

function fetchCompetitorRoutes(url, cb) {
  isCurrentlyFetchingRoutes = true;
  url = url || liveUrl;
  reqwest({
    url: url,
    crossOrigin: true,
    withCredentials: true,
    type: "json",
    success: function (response) {
      if (!response || !response.competitors) {
        // Prevent fetching competitor data for 1 second
        setTimeout(function () {
          isCurrentlyFetchingRoutes = false;
        }, 1000);
        cb && cb();
        return;
      }
      var runnerPoints = [];

      response.competitors.forEach(function (competitor) {
        var route = null;
        if (competitor.encoded_data) {
          route = PositionArchive.fromEncoded(competitor.encoded_data);
          competitorRoutes[competitor.id] = route;
          if (zoomOnRunners) {
            var length = route.getPositionsCount();
            for (var i = 0; i < length; i++) {
              var pt = route.getByIndex(i);
              runnerPoints.push(
                L.latLng([pt.coords.latitude, pt.coords.longitude])
              );
            }
          }
        }
        // if last position is not older than 30 minutes
        if (
          route &&
          route.getLastPosition().timestamp > +new Date() - 30 * 60 * 1e3
        ) {
          competitorBatteyLevels[competitor.id] = competitor.battery_level;
        } else {
          competitorBatteyLevels[competitor.id] = null;
        }
      });

      updateCompetitorList(response.competitors);
      displayCompetitorList();
      routesLastFetched = performance.now();
      lastDataTs = response.timestamp;
      isCurrentlyFetchingRoutes = false;
      if (zoomOnRunners && runnerPoints.length) {
        map.fitBounds(runnerPoints);
        zoomOnRunners = false;
      }
      cb && cb();
    },
    error: function () {
      isCurrentlyFetchingRoutes = false;
    },
  });
}

function refreshEventData() {
  reqwest({
    url: window.local.eventUrl,
    withCredentials: true,
    crossOrigin: true,
    type: "json",
    success: function (response) {
      if (response.error) {
        if (response.error === "No event match this id") {
          window.location.reload();
        }
        return;
      }
      eventDataLastFetch = performance.now();
      endEvent = new Date(response.event.end_date);

      if (new Date(response.event.start_date) != startEvent) {
        var oldStart = startEvent;
        startEvent = new Date(response.event.start_date);
        var startDateTxt = dayjs(startEvent)
          .local()
          .locale(locale)
          .format("LLLL");
        u("#event-start-date-text").text(
          banana.i18n("event-start-date-text", startDateTxt)
        );
        // user changed the event start from past to in the future
        if (oldStart < clock.now() && startEvent > clock.now()) {
          window.location.reload();
          return;
        }
        // user changed the event start from future to in the past
        if (oldStart > clock.now() && startEvent < clock.now()) {
          window.location.reload();
          return;
        }
      }

      if (response.announcement && response.announcement != prevNotice) {
        prevNotice = response.announcement;
        u(".text-alert-content").text(prevNotice);
        toast.show();
      }

      if (
        Array.isArray(response.maps) &&
        JSON.stringify(response.maps) !== prevMapsJSONData
      ) {
        prevMapsJSONData = JSON.stringify(response.maps);
        var currentMapUpdated = response.maps.find(function (m) {
          return (
            rasterMap &&
            m.id === rasterMap.data.id &&
            m.modification_date !== rasterMap.data.modification_date
          );
        });
        var currentMap = response.maps.find(function (m) {
          return rasterMap && m.id === rasterMap.data.id;
        });
        if (rasterMap && (currentMapUpdated || response.maps.length <= 1)) {
          rasterMap.remove();
        }
        if (response.maps.length) {
          var mapChoices = {};
          for (var i = 0; i < response.maps.length; i++) {
            var mapData = response.maps[i];
            mapData.title =
              !mapData.title && mapData.default
                ? '<i class="fa-solid fa-star"></i> Main Map'
                : u("<i/>").text(mapData.title).text();
            var layer = addRasterMapLayer(mapData, i);
            mapChoices[mapData.title] = layer;

            var isSingleMap = response.maps.length === 1;
            var isCurrentMap = currentMap?.id === mapData.id;
            var isItNewDefaultWhenCurrentDeleted =
              !currentMap && mapData.default;
            if (
              isSingleMap ||
              isCurrentMap ||
              isItNewDefaultWhenCurrentDeleted
            ) {
              setRasterMap(layer, currentMapUpdated || isSingleMap);
            }
          }

          if (mapSelectorLayer) {
            mapSelectorLayer.remove();
          }
          if (response.maps.length > 1) {
            mapSelectorLayer = L.control.layers(mapChoices, null, {
              collapsed: false,
            });
            try {
              mapSelectorLayer.addTo(map);
            } catch (e) {}
            map.off("baselayerchange", onLayerChange);
            map.on("baselayerchange", onLayerChange);
          }
        } else {
          u("#toggleMapSwitch").parent().parent().hide();
          mapOpacity = 1;
        }
      }
    },
  });
}

function updateCompetitorList(newList) {
  newList.forEach(updateCompetitor);
}

function setCustomStart(latlng) {
  for (var i = 0; i < competitorList.length; i++) {
    (function (competitor) {
      var minDist = Infinity;
      var minDistT = null;
      var route = competitorRoutes[competitor.id];
      if (route) {
        var length = route.getPositionsCount();
        for (var i = 0; i < length; i++) {
          dist = route.getByIndex(i).distance({
            coords: { latitude: latlng.lat, longitude: latlng.lng },
          });
          if (dist < minDist) {
            minDist = dist;
            minDistT = route.getByIndex(i).timestamp;
          }
        }
        competitor.custom_offset = minDistT;
      }
    })(competitorList[i]);
  }
}

function updateCompetitor(newData) {
  var idx = competitorList.findIndex(function (c) {
    return c.id == newData.id;
  });
  if (idx != -1) {
    var c = competitorList[idx];
    Object.keys(newData).forEach(function (k) {
      c[k] = newData[k];
    });
    competitorList[idx] = c;
  } else {
    competitorList.push(newData);
  }
}

function hideSidebar() {
  u("#map")
    .addClass("col-12")
    .addClass("no-sidebar")
    .removeClass("col-sm-7")
    .removeClass("col-lg-9")
    .removeClass("col-xxl-10");
  u("#sidebar")
    .addClass("d-none")
    .removeClass("col-12")
    .addClass("d-sm-none")
    .removeClass("d-sm-block")
    .removeClass("col-sm-5")
    .removeClass("col-lg-3")
    .removeClass("col-xxl-2");
  sidebarShown = false;
  u("#permanent-sidebar .btn").removeClass("active");
  try {
    map.invalidateSize();
  } catch {}
}

function showSidebar() {
  u("#map")
    .addClass("col-12")
    .addClass("col-sm-7")
    .addClass("col-lg-9")
    .addClass("col-xxl-10")
    .removeClass("no-sidebar");
  u("#sidebar")
    .removeClass("d-none")
    .addClass("col-12")
    .removeClass("d-sm-none")
    .addClass("d-sm-block")
    .addClass("col-sm-5")
    .addClass("col-lg-3")
    .addClass("col-xxl-2");
  sidebarShown = true;
  try {
    map.invalidateSize();
  } catch {}
}

function batteryIconName(perc) {
  if (perc === null) return "half";
  var level = Math.min(4, Math.round((perc - 5) / 20));
  return ["empty", "quarter", "half", "three-quarters", "full"][level];
}

function toggleCompetitorList(e) {
  e.preventDefault();
  var width = window.innerWidth > 0 ? window.innerWidth : screen.width;
  if (
    sidebarShown &&
    !optionDisplayed &&
    !(u("#sidebar").hasClass("d-none") && width <= 576)
  ) {
    // we remove the competitor list
    hideSidebar();
  } else {
    // we add the side bar
    showSidebar();
    displayCompetitorList(true);
    u("#permanent-sidebar .btn").removeClass("active");
    u("#runners_show_button").addClass("active");
  }
}

function toggleCompetitorFullRoute(competitor) {
  if (!competitor.isShown) {
    return;
  }
  if (competitor.displayFullRoute) {
    competitor.displayFullRoute = null;
    competitor.sidebarCard?.find(".full-route-icon").attr({ fill: null });
  } else {
    competitor.displayFullRoute = true;
    competitor.sidebarCard?.find(".full-route-icon").attr({ fill: "#20c997" });
  }
}

function zoomOnCompetitor(compr) {
  if (!compr.isShown || compr.focusing) {
    return;
  }
  compr.focusing = true;
  var route = competitorRoutes[compr.id];
  if (!route) {
    compr.focusing = false;
    return;
  }
  var timeT = currentTime;
  if (!isRealTime) {
    if (isCustomStart) {
      timeT += +new Date(compr.custom_offset) - getCompetitionStartDate();
    } else {
      timeT += +new Date(compr.start_time) - getCompetitionStartDate();
    }
  }
  var loc = route.getByTime(timeT);
  map.setView([loc.coords.latitude, loc.coords.longitude], map.getZoom(), {
    animate: true,
  });
  setTimeout(function () {
    compr.focusing = false;
  }, 250);
}

function redrawCompetitorMarker(competitor, location, faded) {
  var coordinates = [location.coords.latitude, location.coords.longitude];
  if (!competitor.mapMarker) {
    var runnerIcon = getRunnerIcon(
      competitor.color,
      faded,
      competitor.highlighted
    );
    competitor.mapMarker = L.marker(coordinates, { icon: runnerIcon });
    competitor.mapMarker.addTo(map);
  } else {
    competitor.mapMarker.setLatLng(coordinates);
  }
}

function redrawCompetitorNametag(competitor, location, faded) {
  var coordinates = [location.coords.latitude, location.coords.longitude];
  var pointX = map.latLngToContainerPoint(coordinates).x;
  var mapMiddleX = map.getSize().x / 2;
  var nametagOnRightSide = pointX > mapMiddleX;
  var nametagChangeSide =
    competitor.nameMarker &&
    ((competitor.isNameOnRight && !nametagOnRightSide) ||
      (!competitor.isNameOnRight && nametagOnRightSide));
  if (nametagChangeSide) {
    map.removeLayer(competitor.nameMarker);
    competitor.nameMarker = null;
  }
  if (!competitor.nameMarker) {
    competitor.isNameOnRight = nametagOnRightSide;
    var runnerIcon = getRunnerNameMarker(
      competitor.short_name,
      competitor.color,
      competitor.isColorDark,
      nametagOnRightSide,
      faded,
      competitor.highlighted
    );
    competitor.nameMarker = L.marker(coordinates, { icon: runnerIcon });
    competitor.nameMarker.addTo(map);
  } else {
    competitor.nameMarker.setLatLng(coordinates);
  }
}

function redrawCompetitorTail(competitor, route, time) {
  var tail = null;
  var hasPointInTail = false;
  if (competitor.displayFullRoute) {
    tail = route.extractInterval(-Infinity, time);
    hasPointInTail = route.hasPointInInterval(-Infinity, time);
  } else {
    tail = route.extractInterval(time - tailLength * 1e3, time);
    hasPointInTail = route.hasPointInInterval(time - tailLength * 1e3, time);
  }
  if (!hasPointInTail) {
    if (competitor.tail) {
      map.removeLayer(competitor.tail);
    }
    competitor.tail = null;
  } else {
    var tailLatLng = tail
      .getArray()
      .filter(function (pos) {
        return !isNaN(pos.coords.latitude);
      })
      .map(function (pos) {
        return [pos.coords.latitude, pos.coords.longitude];
      });

    if (!competitor.tail) {
      competitor.tail = L.polyline(tailLatLng, {
        color: competitor.color,
        opacity: 0.75,
        weight: 5,
        className: competitor.focused ? "icon-focused" : "",
      }).addTo(map);
    } else {
      competitor.tail.setLatLngs(tailLatLng);
    }
  }
}

function toggleHighlightCompetitor(competitor) {
  const wasHighlighted = competitor.highlighted;
  if (wasHighlighted) {
    competitor.highlighted = false;
    competitor.sidebarCard
      ?.find(".competitor-highlight-btn")
      .removeClass("highlighted");
  } else {
    if (!competitor.isShown) {
      return;
    }
    competitor.highlighted = true;
    competitor.sidebarCard
      ?.find(".competitor-highlight-btn")
      .addClass("highlighted");
  }
  ["mapMarker", "nameMarker", "tail"].forEach(function (layerName) {
    competitor[layerName]?.remove();
    competitor[layerName] = null;
  });
}
function onChangeCompetitorColor(competitor) {
  var color = competitor.color;
  u("#colorModalLabel").text(banana.i18n("select-color-for", competitor.name));
  u("#color-picker").html("");
  new iro.ColorPicker("#color-picker", {
    color,
    width: 150,
    display: "inline-block",
  }).on("color:change", function (c) {
    color = c.hexString;
  });
  colorModal.show();
  u("#save-color").on("click", function () {
    competitor.color = color;
    competitor.isColorDark = getContrastYIQ(competitor.color);
    colorModal.hide();
    ["mapMarker", "nameMarker", "tail"].forEach(function (layerName) {
      competitor[layerName]?.remove();
      competitor[layerName] = null;
    });
    displayCompetitorList();
    u("#save-color").off("click");
  });
}

function displayCompetitorList(force) {
  if (!force && optionDisplayed) {
    return;
  }
  optionDisplayed = false;
  var scrollTopDiv = u("#competitorList").first()?.scrollTop;
  var listDiv = u("<div/>");
  listDiv.addClass("mt-1");
  listDiv.attr({ id: "competitorList" });
  listDiv.css({ overflowY: "auto" });

  nbShown = 0;

  for (var i = 0; i < competitorList.length; i++) {
    (function (competitor) {
      if (typeof competitor.isShown === "undefined") {
        if (nbShown < maxParticipantsDisplayed) {
          competitor.isShown = true;
          nbShown += 1;
        } else {
          competitor.isShown = false;
        }
      }
      if (!competitor.color) {
        competitor.color = getColor(i);
        competitor.isColorDark = getContrastYIQ(competitor.color);
      }
      var div = u("<div/>");
      div.addClass("card-body", "px-1", "pt-1", "pb-0", "competitor-card");
      {
        var firstLine = u("<div/>")
          .addClass("text-nowrap", "text-truncate", "overflow-hidden")
          .css({ lineHeight: "1.13rem" });

        var colorTag = u("<span/>")
          .addClass("color-tag", "me-1")
          .css({ cursor: "pointer" });

        if (competitor.isShown) {
          colorTag.on("click", function () {
            onChangeCompetitorColor(competitor);
          });
        }

        var colorTagIcon = u("<i/>")
          .addClass(
            "media-object",
            "fa-3x",
            "fa-solid",
            "fa-circle",
            "icon-sidebar"
          )
          .css({
            marginLeft: "1px",
            fontSize: "1em",
            color: competitor.color,
          });

        if (competitor.isShown) {
          colorTagIcon.css({
            color: competitor.color,
          });
        } else {
          colorTagIcon.css({
            color: "rgba(250, 250, 250, 0.9)",
          });
        }

        var nameDiv = u("<span/>")
          .addClass("overflow-hidden", "ps-0", "text-truncate", "fw-bold")
          .text(competitor.name);

        colorTag.append(colorTagIcon);
        firstLine.append(colorTag);
        firstLine.append(nameDiv);
        div.append(firstLine);
      }
      {
        var secondLine = u("<div/>").addClass(
          "text-nowrap",
          "text-truncate",
          "overflow-hidden",
          "ps-0",
          competitor.isShown ? "route-displayed" : "route-not-displayed"
        );

        {
          var competitorSwitch = u("<div/>")
            .addClass(
              "form-check",
              "form-switch",
              "d-inline-block",
              "align-middle"
            )
            .css({ marginRight: "-5px", paddingTop: "2px" })
            .attr({
              "data-bs-toggle": "tooltip",
              "data-bs-title": banana.i18n("toggle"),
            });

          var competitorSwitchInput = u("<input/>")
            .addClass("form-check-input", "competitor-switch")
            .css({ boxShadow: "none" })
            .attr({
              type: "checkbox",
              checked: !!competitor.isShown,
            })
            .on("click", function (e) {
              var commonDiv = u(this).parent().parent();
              if (!e.target.checked) {
                competitor.isShown = false;
                competitor.focused = false;
                competitor.highlighted = false;
                competitor.displayFullRoute = null;
                commonDiv.find(".competitor-focus-btn").removeClass("focused");
                commonDiv
                  .find(".competitor-highlight-btn")
                  .removeClass("highlighted");
                commonDiv.find(".full-route-icon").attr({ fill: null });
                commonDiv.find("button").attr({ disabled: true });
                commonDiv
                  .removeClass("route-displayed")
                  .addClass("route-not-displayed");

                var colorTag = commonDiv.parent().find(".color-tag");
                colorTag
                  .find("i.fa-circle")
                  .css({ color: "rgba(250, 250, 250, 0.9)" });
                colorTag.off("click");

                ["mapMarker", "nameMarker", "tail"].forEach(function (
                  layerName
                ) {
                  competitor[layerName]?.remove();
                  competitor[layerName] = null;
                });
                commonDiv.find(".speedometer").text("");
                commonDiv.find(".odometer").text("");
                competitor.speedometerValue = "";
                competitor.odometerValue = "";
                updateCompetitor(competitor);
                nbShown -= 1;
              } else {
                if (nbShown >= maxParticipantsDisplayed) {
                  swal({
                    title: banana.i18n(
                      "reached-max-runners",
                      maxParticipantsDisplayed
                    ),
                    type: "error",
                    confirmButtonText: "OK",
                  });
                  return;
                }
                competitor.isShown = true;
                commonDiv
                  .removeClass("route-not-displayed")
                  .addClass("route-displayed");
                commonDiv.find("button").attr({ disabled: false });

                var colorTag = commonDiv.parent().find(".color-tag");
                colorTag.find("i.fa-circle").css({ color: competitor.color });
                colorTag.on("click", function () {
                  onChangeCompetitorColor(competitor);
                });

                updateCompetitor(competitor);
                nbShown += 1;
              }
            });

          competitorSwitch.append(competitorSwitchInput);
          secondLine.append(competitorSwitch);
        }

        {
          var competitorCenterBtn = u("<button/>")
            .addClass("btn", "btn-default", "btn-sm", "p-0", "ms-1", "me-0")
            .attr({
              "aria-label": "Center",
              "data-bs-toggle": "tooltip",
              "data-bs-title": banana.i18n("center"),
              disabled: !competitor.isShown,
            })
            .on("click", function () {
              zoomOnCompetitor(competitor);
            });

          var competitorCenterIcon = u("<i/>").addClass(
            "fa-solid",
            "fa-location-dot"
          );

          competitorCenterBtn.append(competitorCenterIcon);
          secondLine.append(competitorCenterBtn);
        }

        {
          var competitorFollowBtn = u("<button/>")
            .addClass(
              "btn",
              "btn-default",
              "btn-sm",
              "p-0",
              "ms-1",
              "me-0",
              "competitor-focus-btn",
              competitor.focused ? "focused" : ""
            )
            .attr({
              "aria-label": "Follow competitor",
              "data-bs-toggle": "tooltip",
              "data-bs-title": banana.i18n("follow"),
              disabled: !competitor.isShown,
            })
            .on("click", function () {
              const wasFocused = competitor.focused;
              if (wasFocused) {
                competitor.focused = false;
                competitor.sidebarCard
                  ?.find(".competitor-focus-btn")
                  .removeClass("focused");
              } else {
                if (!competitor.isShown) {
                  return;
                }
                competitorList.map((otherCompetitor) => {
                  if (otherCompetitor.focused) {
                    otherCompetitor.focused = false;
                    otherCompetitor.sidebarCard
                      ?.find(".competitor-focus-btn")
                      .removeClass("focused");
                  }
                });
                competitor.focused = true;
                competitor.sidebarCard
                  ?.find(".competitor-focus-btn")
                  .addClass("focused");
                zoomOnCompetitor(competitor);
              }
            });

          var competitorFollowBtnIcon = u("<i/>").addClass(
            "fa-solid",
            "fa-crosshairs"
          );

          competitorFollowBtn.append(competitorFollowBtnIcon);
          secondLine.append(competitorFollowBtn);
        }

        {
          var competitorHighlightBtn = u("<button/>")
            .addClass(
              "btn",
              "btn-default",
              "btn-sm",
              "p-0",
              "ms-1",
              "me-0",
              "competitor-highlight-btn",
              competitor.highlighted ? " highlighted" : ""
            )
            .attr({
              "aria-label": "Highlight competitor",
              "data-bs-toggle": "tooltip",
              "data-bs-title": banana.i18n("highlight"),
              disabled: !competitor.isShown,
            })
            .on("click", function () {
              toggleHighlightCompetitor(competitor);
            });

          var competitorHighlightIcon = u("<i/>").addClass(
            "fa-solid",
            "fa-highlighter"
          );

          competitorHighlightBtn.append(competitorHighlightIcon);
          secondLine.append(competitorHighlightBtn);
        }

        {
          var competitorFullRouteBtn = u("<button/>")
            .addClass(
              "btn",
              "btn-default",
              "btn-sm",
              "p-0",
              "ms-1",
              "me-0",
              "competitor-full-route-btn",
              competitor.displayFullRoute ? "full-route" : ""
            )
            .attr({
              "aria-label": "Display competitor's full Route",
              "data-bs-toggle": "tooltip",
              "data-bs-title": banana.i18n("full-route"),
              disabled: !competitor.isShown,
            })
            .on("click", function () {
              toggleCompetitorFullRoute(competitor);
            });

          var competitorFullRouteBtnIcon = u("<svg/>")
            .addClass("full-route-icon")
            .attr({
              fill: competitor.displayFullRoute ? "#20c997" : null,
              viewBox: "0 0 48 48",
              width: "16px",
              height: "16px",
              xmlns: "http://www.w3.org/2000/svg",
            })
            .css({ verticalAlign: "text-bottom" })
            .html(
              '<path d="M28.65 42.95q-2.85 0-4.775-2.075Q21.95 38.8 21.95 35.45q0-2.5 1.325-4.4 1.325-1.9 3.125-3.1 1.8-1.2 3.7-1.825 1.9-.625 3.2-.675-.15-2.4-1.1-3.475-.95-1.075-2.75-1.075-2 0-3.7 1.15-1.7 1.15-4.5 5.1-2.85 4.05-5.075 5.65-2.225 1.6-4.675 1.6-2.5 0-4.475-1.625Q5.05 31.15 5.05 27.15q0-1.45 1.025-3.7T9.65 17.2q1.9-2.55 2.5-3.725.6-1.175.6-2.175 0-.55-.325-.875-.325-.325-.925-.325-.3 0-.8.15t-1 .6q-1 .55-1.825.525-.825-.025-1.375-.625-.7-.55-.7-1.525 0-.975.7-1.625 1.15-1 2.475-1.55Q10.3 5.5 11.75 5.5q2.35 0 3.9 1.65Q17.2 8.8 17.2 11q0 2.25-.95 4.15-.95 1.9-3.2 5.15-2.25 3.4-2.875 4.625T9.55 27.45q0 1.35.775 1.775.775.425 1.625.425 1.2 0 2.4-1.125t3.55-4.275q3.35-4.4 6-6.175 2.65-1.775 5.95-1.775 3.15 0 5.425 2.275T37.85 25.3h2.9q1 0 1.625.625T43 27.5q0 1-.625 1.65-.625.65-1.625.65h-2.9q-.55 8.8-3.9 10.975-3.35 2.175-5.3 2.175Zm.15-4.65q1.05 0 2.6-1.525t1.95-6.725q-1.9.2-4.375 1.55T26.5 35.95q0 1.1.575 1.725t1.725.625Z"/>'
            );

          competitorFullRouteBtn.append(competitorFullRouteBtnIcon);
          secondLine.append(competitorFullRouteBtn);
        }

        if (competitorBatteyLevels.hasOwnProperty(competitor.id)) {
          var batteryLevelDiv = u("<div/>").addClass(
            "float-end",
            "d-inline-blockv",
            "text-end",
            "if-live",
            !isLiveMode ? "d-none" : ""
          );

          var batterySpan = u("<span/>").attr({
            "data-bs-toggle": "tooltip",
            "data-bs-custom-class": "higher-z-index",
            "data-bs-title":
              competitorBatteyLevels[competitor.id] !== null
                ? competitorBatteyLevels[competitor.id] + "%"
                : banana.i18n("unknown"),
          });

          var batteryIcon = u("<i/>").addClass(
            "fa-solid",
            "fa-rotate-270",
            `fa-battery-${batteryIconName(
              competitorBatteyLevels[competitor.id]
            )}`
          );

          batterySpan.append(batteryIcon);
          batteryLevelDiv.append(batterySpan);
          secondLine.append(batteryLevelDiv);
        }

        {
          var metersDiv = u("<div/>")
            .addClass("float-end d-inline-block text-end")
            .css({ lineHeight: "10px" });
          var speedometer = u("<span/>")
            .addClass("speedometer")
            .text(!competitor.isShown ? "" : competitor.speedometerValue || "");
          var odometer = u("<span/>")
            .addClass("odometer")
            .text(!competitor.isShown ? "" : competitor.odometerValue || "");
          metersDiv.append(speedometer).append("<br/>").append(odometer);

          secondLine.append(metersDiv);
        }
        div.append(secondLine);
      }

      competitor.sidebarCard = div;
      competitor.speedometer = div.find(".speedometer").first();
      competitor.odometer = div.find(".odometer").first();

      if (
        searchText === null ||
        searchText === "" ||
        competitor.name.toLowerCase().search(searchText) != -1
      ) {
        var divOneUp = u(
          '<div class="card mb-1" style="background-color:transparent;"/>'
        ).append(div);
        listDiv.append(divOneUp);
      }
    })(competitorList[i]);
  }
  if (competitorList.length === 0) {
    var div = u(
      '<div class="no-competitor-warning text-center d-flex justify-content-center align-items-center"/>'
    );
    div.append(
      u("<h3/>").html(
        '<i class="fa-solid fa-triangle-exclamation"></i><br/>' +
          banana.i18n("no-competitors")
      )
    );
    listDiv.append(div);
  }
  if (!searchText) {
    var mainDiv = u('<div id="competitorSidebar" class="d-flex flex-column"/>');
    var topDiv = u("<div/>");
    var searchBar = u("<form/>").addClass("row g-0 flex-nowrap");
    if (competitorList.length) {
      var toggleAllContent = u("<div/>").addClass(
        "form-group",
        "form-check",
        "form-switch",
        "d-inline-block",
        "ms-1",
        "col-auto",
        "pt-2",
        "me-0",
        "pe-0"
      );
      var toggleAllInput = u("<input/>")
        .addClass("form-check-input")
        .attr({
          id: "toggleAllSwitch",
          type: "checkbox",
          checked: !!showAll,
        })
        .on("click", function (e) {
          showAll = !!e.target.checked;
          if (showAll) {
            nbShown = competitorList.reduce(function (a, v) {
              return v.isShown ? a + 1 : a;
            }, 0);
            var didNotShowAll = false;
            for (var i = 0; i < competitorList.length; i++) {
              var competitor = competitorList[i];
              if (nbShown >= maxParticipantsDisplayed && !competitor.isShown) {
                didNotShowAll = true;
              } else if (!competitor.isShown) {
                nbShown += 1;
                competitor.isShown = true;
              }
              updateCompetitor(competitor);
            }
            if (didNotShowAll) {
              swal({
                title: banana.i18n(
                  "reached-max-runners",
                  maxParticipantsDisplayed
                ),
                type: "warning",
                confirmButtonText: "OK",
              });
            }
          } else {
            for (var i = 0; i < competitorList.length; i++) {
              var competitor = competitorList[i];
              competitor.isShown = false;
              competitor.focused = false;
              competitor.highlighted = false;
              competitor.displayFullRoute = false;
              ["mapMarker", "nameMarker", "tail"].forEach(function (layerName) {
                competitor[layerName]?.remove();
                competitor[layerName] = null;
              });
              updateCompetitor(competitor);
              nbShown = 0;
            }
          }
          displayCompetitorList();
        });
      searchBar.append(toggleAllContent.append(toggleAllInput));
      searchBar.append(
        u("<div>")
          .addClass("col-auto flex-fill ms-0 ps-0")
          .append(
            u('<input class="form-control" type="search" val=""/>')
              .on("input", filterCompetitorList)
              .attr("placeholder", banana.i18n("search-competitors"))
          )
      );
      topDiv.append(searchBar);
    }
    mainDiv.append(topDiv);
    mainDiv.append(listDiv);
    u("#sidebar").html("");
    u("#sidebar").append(mainDiv);
  } else {
    u("#competitorList").remove();
    var mainDiv = u("#competitorSidebar");
    mainDiv.append(listDiv);
  }
  if (competitorList.length == 0) {
    listDiv.addClass("without-competitor");
  }
  if (scrollTopDiv) {
    listDiv.nodes[0].scrollTop = scrollTopDiv;
  }
  u(".tooltip").remove();
  const tooltipEls = u("#competitorSidebar").find('[data-bs-toggle="tooltip"]');
  tooltipEls.map((el) => new bootstrap.Tooltip(el, { trigger: "hover" }));
}

function filterCompetitorList(e) {
  var inputVal = u(e.target).val();
  searchText = inputVal.toLowerCase();
  displayCompetitorList();
}

function displayOptions(ev) {
  ev.preventDefault();
  if (optionDisplayed) {
    // hide sidebar
    optionDisplayed = false;
    hideSidebar();
    displayCompetitorList();
    return;
  }
  var width = window.innerWidth > 0 ? window.innerWidth : screen.width;
  // show sidebar
  if (!sidebarShown || (u("#sidebar").hasClass("d-none") && width <= 576)) {
    showSidebar();
  }
  u("#permanent-sidebar .btn").removeClass("active");
  u("#options_show_button").addClass("active");
  optionDisplayed = true;
  searchText = null;
  var optionsSidebar = u("<div/>");
  optionsSidebar.css({
    "overflow-y": "auto",
    "overflow-x": "hidden",
  });
  optionsSidebar.attr({ id: "optionsSidebar" });

  {
    var tailLenWidget = u("<div/>").addClass("mb-2");

    var widgetTitle = u("<h4/>")
      .text(banana.i18n("tails"))
      .addClass("text-nowrap");

    var widgetContent = u("<div/>").addClass("form-group");

    var tailLenLabel = u("<label/>").text(banana.i18n("length-in-seconds"));

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

    tailLenFormDiv.find(".tailLengthControl").on("input", function (e) {
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
      tailLength = Math.max(0, v);
      hourInput.val(Math.floor(tailLength / 3600));
      minInput.val(Math.floor((tailLength / 60) % 60));
      secInput.val(Math.floor(tailLength % 60));
      u("#tail-length-display").text(printTime(tailLength));
    });
    widgetContent.append(tailLenLabel).append(tailLenFormDiv);

    tailLenWidget.append(widgetTitle).append(widgetContent);

    optionsSidebar.append(tailLenWidget);
  }
  {
    var ctrlWidget = u("<div/>").addClass("mb-2");

    var widgetTitle = u("<h4/>")
      .text(banana.i18n("map-controls"))
      .addClass("text-nowrap");

    var widgetContent = u("<div/>").addClass(
      "form-check",
      "form-switch",
      "d-inline-block",
      "ms-1"
    );

    var widgetInput = u("<input/>")
      .addClass("form-check-input")
      .attr({
        id: "toggleControlsSwitch",
        type: "checkbox",
        checked: !!showControls,
      })
      .on("click", function (e) {
        if (!e.target.checked) {
          showControls = false;
          panControl.remove();
          zoomControl.remove();
          rotateControl.remove();
        } else {
          map.addControl(panControl);
          map.addControl(zoomControl);
          map.addControl(rotateControl);
          showControls = true;
        }
      });
    var widgetLabel = u("<label/>")
      .addClass("form-check-label")
      .attr({ for: "toggleControlsSwitch" })
      .text(banana.i18n("show-map-controls"));

    widgetContent.append(widgetInput).append(widgetLabel);

    ctrlWidget.append(widgetTitle).append(widgetContent);

    optionsSidebar.append(ctrlWidget);
  }
  {
    var groupWidget = u("<div/>").addClass("mb-2");

    var widgetTitle = u("<h4/>")
      .text(banana.i18n("groupings"))
      .addClass("text-nowrap");

    var widgetContent = u("<div/>").addClass(
      "form-check",
      "form-switch",
      "d-inline-block",
      "ms-1"
    );

    var widgetInput = u("<input/>")
      .addClass("form-check-input")
      .attr({
        id: "toggleClusterSwitch",
        type: "checkbox",
        checked: !!showClusters,
      })
      .on("click", function (e) {
        if (!e.target.checked) {
          showClusters = false;
          groupControl.remove();
          for (var [key, cluster] of Object.entries(clusters)) {
            ["mapMarker", "nameMarker"].forEach(function (layerName) {
              if (cluster[layerName]) {
                cluster[layerName]?.remove();
                clusters[key][layerName] = null;
              }
            });
          }
          clusters = {};
        } else {
          groupControl = L.control.grouping({ position: "topright" });
          map.addControl(groupControl);
          showClusters = true;
        }
      });
    var widgetLabel = u("<label/>")
      .addClass("form-check-label")
      .attr({ for: "toggleClusterSwitch" })
      .text(banana.i18n("show-groupings"));

    widgetContent.append(widgetInput).append(widgetLabel);

    groupWidget.append(widgetTitle).append(widgetContent);

    optionsSidebar.append(groupWidget);
  }
  {
    var langWidget = u("<div/>").addClass("mb-2");

    var widgetTitle = u("<h4/>")
      .addClass("text-nowrap")
      .html(`<i class="fa-solid fa-language"></i> ${banana.i18n("language")}`);

    var langSelector = u("<select/>")
      .addClass("form-select")
      .attr({ ariaLabel: "Language" })
      .on("change", function (e) {
        window.localStorage.setItem("lang", e.target.value);
        window.location.search = `lang=${e.target.value}`;
      });

    Object.keys(supportedLanguages).forEach(function (lang) {
      var option = u("<option/>");
      option.attr({ value: lang });
      option.text(supportedLanguages[lang]);
      if (locale === lang) {
        option.attr({ selected: true });
      }
      langSelector.append(option);
    });

    langWidget.append(widgetTitle).append(langSelector);

    optionsSidebar.append(langWidget);
  }
  {
    var locWidget = u("<div/>").addClass("mb-2");

    var widgetTitle = u("<h4/>")
      .text(banana.i18n("location"))
      .addClass("text-nowrap");

    var widgetContent = u("<div/>").addClass(
      "form-check",
      "form-switch",
      "d-inline-block",
      "ms-1"
    );

    var widgetInput = u("<input/>")
      .addClass("form-check-input")
      .attr({
        id: "toggleLocationSwitch",
        type: "checkbox",
        checked: !!showUserLocation,
      })
      .on("click", function (e) {
        showUserLocation = e.target.checked;
        if (!showUserLocation) {
          locateControl.stop();
        } else {
          locateControl.start();
        }
      });
    var widgetLabel = u("<label/>")
      .addClass("form-check-label")
      .attr({ for: "toggleLocationSwitch" })
      .text(banana.i18n("show-location"));

    widgetContent.append(widgetInput).append(widgetLabel);

    locWidget.append(widgetTitle).append(widgetContent);

    optionsSidebar.append(locWidget);
  }

  if (rasterMap) {
    var toggleMapWidget = u("<div/>").addClass("mb-2");

    var widgetTitle = u("<h4/>")
      .text(banana.i18n("map"))
      .addClass("text-nowrap");

    var widgetContent = u("<div/>").addClass(
      "form-check",
      "form-switch",
      "d-inline-block",
      "ms-1"
    );

    var widgetInput = u("<input/>")
      .addClass("form-check-input")
      .attr({
        id: "toggleMapSwitch",
        type: "checkbox",
        checked: mapOpacity === 0,
      })
      .on("click", function (e) {
        if (mapOpacity === 0) {
          mapOpacity = 1;
        } else {
          mapOpacity = 0;
        }
        rasterMap?.setOpacity(mapOpacity);
      });
    var widgetLabel = u("<label/>")
      .addClass("form-check-label")
      .attr({ for: "toggleMapSwitch" })
      .text(banana.i18n("hide-map"));

    widgetContent.append(widgetInput).append(widgetLabel);

    toggleMapWidget.append(widgetTitle).append(widgetContent);

    optionsSidebar.append(toggleMapWidget);
  }

  {
    var bgMapWidget = u("<div/>").addClass("mb-2");

    var widgetTitle = u("<h4/>")
      .text(banana.i18n("background-map"))
      .addClass("text-nowrap");

    var mapSelector = u("<select/>")
      .addClass("form-select")
      .attr({ ariaLabel: "Background map" })
      .on("change", function (e) {
        if (backgroundLayer) {
          backgroundLayer.remove();
          backgroundLayer = null;
        }
        if (e.target.value === "blank") {
          u("#map").css({ background: "#fff" });
        } else {
          u("#map").css({ background: "#ddd" });
          var layer = backdropMaps[e.target.value];
          layer.nickname = e.target.value;
          layer.setZIndex(-1);
          layer.addTo(map);
          backgroundLayer = layer;
        }
      });

    var blankOption = u("<option/>");
    blankOption.attr({ value: "blank" });
    blankOption.text("Blank");
    if (!backgroundLayer) {
      blankOption.attr({ selected: true });
    }
    mapSelector.append(blankOption);

    Object.entries(backgroundMapTitles).forEach(function (kv) {
      var option = u("<option/>");
      option.attr({ value: kv[0] });
      option.text(kv[1]);
      if (backgroundLayer?.nickname === kv[0]) {
        option.attr({ selected: true });
      }
      mapSelector.append(option);
    });

    bgMapWidget.append(widgetTitle).append(mapSelector);

    optionsSidebar.append(bgMapWidget);
  }

  if (qrUrl) {
    var qr = new QRious();
    qr.set({
      background: "#f5f5f5",
      foreground: "black",
      level: "L",
      value: qrUrl,
      size: 138,
    });

    var qrWidget = u("<div/>").addClass("mb-2");

    var widgetTitle = u("<h4/>")
      .text(banana.i18n("qr-link"))
      .addClass("text-nowrap");

    qrWidget.append(widgetTitle);

    var widgetContent = u("<p/>").addClass("text-center");

    var qrImage = u("<img/>").attr({
      src: qr.toDataURL(),
      alt: "QR code for this event",
    });

    var qrText = u("<a/>")
      .addClass("small", "fw-bold")
      .css({ wordBreak: "break-all" })
      .attr({ href: qrUrl })
      .text(qrUrl.replace(/^https?:\/\//, ""));

    widgetContent.append(qrImage).append(u("<br/>")).append(qrText);

    qrWidget.append(widgetContent);

    optionsSidebar.append(qrWidget);
  }

  u("#sidebar").html("");
  u("#sidebar").append(optionsSidebar);
}

function keepFocusOnCompetitor(competitor, location) {
  var coordinates = [location.coords.latitude, location.coords.longitude];
  const mapSize = map.getSize();
  const placeXY = map.latLngToContainerPoint(coordinates);
  if (
    (placeXY.x < mapSize.x / 4 ||
      placeXY.x > (mapSize.x * 3) / 4 ||
      placeXY.y < mapSize.y / 4 ||
      placeXY.y > (mapSize.y * 3) / 4) &&
    mapSize.x > 0 &&
    mapSize.y > 0
  ) {
    zoomOnCompetitor(competitor);
  }
}

function getRelativeTime(currentTime) {
  var viewedTime = currentTime;
  if (!isRealTime) {
    if (isCustomStart) {
      viewedTime -= getCompetitorsMinCustomOffset() + getCompetitionStartDate();
    } else {
      viewedTime -= getCompetitionStartDate();
    }
  }
  return viewedTime;
}

function getProgressBarText(currentTime, bg = false, date = false) {
  var result = "";
  if (bg && isLiveMode) {
    return "";
  }
  var viewedTime = currentTime;
  if (!isRealTime) {
    if (currentTime === 0) {
      return "00:00:00";
    }
    if (isCustomStart) {
      viewedTime -= getCompetitorsMinCustomOffset() + getCompetitionStartDate();
    } else {
      viewedTime -= getCompetitionStartDate();
    }
    var t = viewedTime / 1e3;

    function to2digits(x) {
      return ("0" + Math.floor(x)).slice(-2);
    }
    result += t > 3600 || bg ? Math.floor(t / 3600) + ":" : "";
    result += to2digits((t / 60) % 60) + ":" + to2digits(t % 60);
  } else {
    var t = Math.round(viewedTime / 1e3);
    if (t === 0) {
      return "00:00:00";
    }

    if (date) {
      result = dayjs(viewedTime).format("YYYY-MM-DD HH:mm:ss");
      if (bg) {
        result = result.replace(" ", "<br/>");
      }
    } else {
      result = dayjs(viewedTime).format("HH:mm:ss");
    }
  }
  return result;
}

function formatSpeed(s) {
  var min = Math.floor(s / 60);
  var sec = Math.floor(s % 60);
  if (min > 99) {
    return "--'--\"/km";
  }
  return min + "'" + ("0" + sec).slice(-2) + '"/km';
}

function checkVisible(elem) {
  if (!sidebarShown) {
    return false;
  }
  var bcr = elem.getBoundingClientRect();
  const elemCenter = {
    x: bcr.left + elem.offsetWidth / 2,
    y: bcr.top + elem.offsetHeight / 2,
  };
  if (elemCenter.y < 0) {
    return false;
  }
  if (
    elemCenter.y > (document.documentElement.clientHeight || window.innerHeight)
  ) {
    return false;
  }
  return true;
}

function clearCompetitorLayers(competitor) {
  ["mapMarker", "nameMarker", "tail"].forEach(function (layerName) {
    if (competitor[layerName]) {
      map.removeLayer(competitor[layerName]);
    }
    competitor[layerName] = null;
  });
}

function drawCompetitors(refreshMeters) {
  // play/pause button
  if (playbackPaused) {
    var html = '<i class="fa-solid fa-play fa-fw"></i> x' + playbackRate;
    if (u("#play_pause_button").html() != html) {
      u("#play_pause_button").html(html);
    }
  } else {
    var html = '<i class="fa-solid fa-pause fa-fw"></i> x' + playbackRate;
    if (u("#play_pause_button").html() != html) {
      u("#play_pause_button").html(html);
    }
  }
  onAppResize();
  // progress bar
  var perc = 0;
  if (isRealTime) {
    perc = isLiveMode
      ? 100
      : ((currentTime - getCompetitionStartDate()) /
          (Math.min(+clock.now(), getCompetitionEndDate()) -
            getCompetitionStartDate())) *
        100;
  } else {
    if (isCustomStart) {
      perc =
        ((currentTime -
          (getCompetitionStartDate() + getCompetitorsMinCustomOffset())) /
          getCompetitorsMaxDuration(true)) *
        100;
    } else {
      perc =
        ((currentTime - getCompetitionStartDate()) /
          getCompetitorsMaxDuration()) *
        100;
    }
    perc = Math.max(0, Math.min(100, perc));
    if (getCompetitionStartDate(true) === null) {
      perc = 100;
    }
  }
  u("#progress_bar")
    .css({ width: perc + "%" })
    .attr("aria-valuenow", perc);
  u("#progress_bar_text").text(getProgressBarText(currentTime));
  u("#big-clock").html(getProgressBarText(currentTime, true, true));

  if (isMapMoving) return;

  var oldFinishCrosses = finishLineCrosses.slice();
  finishLineCrosses = [];

  for (var i = 0; i < competitorList.length; i++) {
    (function (competitor) {
      if (!competitor.isShown) {
        return;
      }
      var route = competitorRoutes[competitor.id];
      if (route !== undefined) {
        var viewedTime = currentTime;
        if (
          !isLiveMode &&
          !isRealTime &&
          !isCustomStart &&
          competitor.start_time
        ) {
          viewedTime +=
            new Date(competitor.start_time) - getCompetitionStartDate();
        } else if (
          !isLiveMode &&
          !isRealTime &&
          isCustomStart &&
          competitor.custom_offset
        ) {
          viewedTime += Math.max(
            0,
            new Date(competitor.custom_offset) - getCompetitionStartDate()
          );
        }
        var loc = route.getByTime(viewedTime);
        var hasPointLast30sec = route.hasPointInInterval(
          viewedTime - 30 * 1e3,
          viewedTime
        );
        if (competitor.focused) {
          keepFocusOnCompetitor(competitor, loc);
        }

        var beforeFirstPoint = route.getByIndex(0).timestamp > viewedTime;
        if (beforeFirstPoint) {
          clearCompetitorLayers(competitor);
        }

        var isIdle =
          viewedTime > route.getByIndex(0).timestamp && !hasPointLast30sec;
        if ((isIdle && !competitor.idle) || (!isIdle && competitor.idle)) {
          competitor.idle = isIdle;
          clearCompetitorLayers(competitor);
        }
        if (!beforeFirstPoint && loc && !isNaN(loc.coords.latitude)) {
          redrawCompetitorMarker(competitor, loc, isIdle);
          redrawCompetitorNametag(competitor, loc, isIdle);
        }
        redrawCompetitorTail(competitor, route, viewedTime);
        if (refreshMeters) {
          // odometer and speedometer
          var hasPointInTail = route.hasPointInInterval(
            viewedTime - 30 * 1e3,
            viewedTime
          );
          if (!hasPointInTail) {
            competitor.speedometerValue = "--'--\"/km";
            competitor.speedometer.textContent = competitor.speedometerValue;
          } else {
            if (checkVisible(competitor.speedometer)) {
              var distance = 0;
              var prevPos = null;
              var tail30s = route.extractInterval(
                viewedTime - 30 * 1e3,
                viewedTime
              );
              tail30s.getArray().forEach(function (pos) {
                if (prevPos && !isNaN(pos.coords.latitude)) {
                  distance += pos.distance(prevPos);
                }
                prevPos = pos;
              });
              var speed = (30 / distance) * 1000;
              competitor.speedometerValue = formatSpeed(speed);
              competitor.speedometer.textContent = competitor.speedometerValue;
            }
          }
          if (checkVisible(competitor.odometer)) {
            var totalDistance = route.distanceUntil(viewedTime);
            competitor.odometerValue = (totalDistance / 1000).toFixed(1) + "km";
            competitor.odometer.textContent = competitor.odometerValue;
          }

          // Splitimes
          if (finishLineSet) {
            if (
              u("#crossing-time").nodes.length &&
              oldCrossingForNTimes !== u("#crossing-time").val()
            ) {
              oldCrossingForNTimes = u("#crossing-time").val() || 1;
              oldFinishCrosses = [];
              finishLineCrosses = [];
            }
            var allPoints = route.getArray();
            var oldCrossing = oldFinishCrosses.find(function (el) {
              return el.competitor.id === competitor.id;
            });
            var useOldCrossing = false;
            var crossCount = 0;
            if (oldCrossing) {
              var oldTs = allPoints[oldCrossing.idx].timestamp;
              if (viewedTime >= oldTs) {
                if (
                  L.LineUtil.segmentsIntersect(
                    map.project(finishLinePoints[0], intersectionCheckZoom),
                    map.project(finishLinePoints[1], intersectionCheckZoom),
                    map.project(
                      L.latLng([
                        allPoints[oldCrossing.idx].coords.latitude,
                        allPoints[oldCrossing.idx].coords.longitude,
                      ]),
                      intersectionCheckZoom
                    ),
                    map.project(
                      L.latLng([
                        allPoints[oldCrossing.idx - 1].coords.latitude,
                        allPoints[oldCrossing.idx - 1].coords.longitude,
                      ]),
                      intersectionCheckZoom
                    )
                  )
                ) {
                  crossCount++;
                  if (crossCount == oldCrossingForNTimes) {
                    var competitorTime = allPoints[oldCrossing.idx].timestamp;
                    if (
                      !isLiveMode &&
                      !isRealTime &&
                      !isCustomStart &&
                      competitor.start_time
                    ) {
                      competitorTime -=
                        new Date(competitor.start_time) -
                        getCompetitionStartDate();
                    }
                    if (
                      !isLiveMode &&
                      !isRealTime &&
                      isCustomStart &&
                      competitor.custom_offset
                    ) {
                      competitorTime -= Math.max(
                        0,
                        new Date(competitor.custom_offset) -
                          getCompetitionStartDate()
                      );
                    }
                    if (getRelativeTime(competitorTime) > 0) {
                      finishLineCrosses.push({
                        competitor: competitor,
                        time: competitorTime,
                        idx: oldCrossing.idx,
                      });
                      useOldCrossing = true;
                    }
                  }
                }
              }
            }
            if (!useOldCrossing) {
              var crossCount = 0;
              for (var i = 1; i < allPoints.length; i++) {
                var tPoint = allPoints[i];
                if (viewedTime < tPoint.timestamp) {
                  break;
                }
                if (
                  L.LineUtil.segmentsIntersect(
                    map.project(finishLinePoints[0], intersectionCheckZoom),
                    map.project(finishLinePoints[1], intersectionCheckZoom),
                    map.project(
                      L.latLng([
                        tPoint.coords.latitude,
                        tPoint.coords.longitude,
                      ]),
                      intersectionCheckZoom
                    ),
                    map.project(
                      L.latLng([
                        allPoints[i - 1].coords.latitude,
                        allPoints[i - 1].coords.longitude,
                      ]),
                      intersectionCheckZoom
                    )
                  )
                ) {
                  crossCount++;
                  if (crossCount == oldCrossingForNTimes) {
                    var competitorTime = tPoint.timestamp;
                    if (
                      !isLiveMode &&
                      !isRealTime &&
                      !isCustomStart &&
                      competitor.start_time
                    ) {
                      competitorTime -=
                        new Date(competitor.start_time) -
                        getCompetitionStartDate();
                    }
                    if (
                      !isLiveMode &&
                      !isRealTime &&
                      isCustomStart &&
                      competitor.custom_offset
                    ) {
                      competitorTime -= Math.max(
                        0,
                        new Date(competitor.custom_offset) -
                          getCompetitionStartDate()
                      );
                    }
                    if (getRelativeTime(competitorTime) > 0) {
                      finishLineCrosses.push({
                        competitor: competitor,
                        time: competitorTime,
                        idx: i,
                      });
                      break;
                    }
                  }
                }
              }
            }
          }
        }
      }
    })(competitorList[i]);
  }

  // Create cluster
  if (showClusters) {
    var competitorsWithMarker = [];
    var competitorsLocations = [];
    for (var i = 0; i < competitorList.length; i++) {
      (function (competitor) {
        if (competitor.mapMarker) {
          competitorsWithMarker.push(competitor);
          var latLon = competitor.mapMarker.getLatLng();
          competitorsLocations.push({
            location: {
              accuracy: 0,
              latitude: latLon.lat,
              longitude: latLon.lng,
            },
          });
        }
      })(competitorList[i]);
    }
    var dbscanner = jDBSCAN()
      .eps(0.015)
      .minPts(1)
      .distance("HAVERSINE")
      .data(competitorsLocations);
    var competitorClusters = dbscanner();
    var clustersCenter = dbscanner.getClusters();

    Object.keys(clusters).forEach(function (key) {
      if (competitorClusters.indexOf(key) === -1) {
        ["mapMarker", "nameMarker"].forEach(function (layerName) {
          if (clusters[key][layerName]) {
            map.removeLayer(clusters[key][layerName]);
            clusters[key][layerName] = null;
          }
        });
      }
    });

    competitorClusters.forEach(function (d, i) {
      if (d != 0) {
        var cluster = clusters[d] || {};
        var clusterCenter = clustersCenter[d - 1];
        if (!cluster.color) {
          cluster.color = getColor(d - 1);
          cluster.isColorDark = getContrastYIQ(cluster.color);
        }
        var competitorInCluster = competitorsWithMarker[i];
        ["mapMarker", "nameMarker"].forEach(function (layerName) {
          if (competitorInCluster[layerName]) {
            map.removeLayer(competitorInCluster[layerName]);
          }
          competitorInCluster[layerName] = null;
        });
        cluster.name = `${banana.i18n("group")} ${alphabetizeNumber(d - 1)}`;
        cluster.short_name = cluster.name;
        var clusterLoc = { coords: clusterCenter.location };
        redrawCompetitorMarker(cluster, clusterLoc, false);
        redrawCompetitorNametag(cluster, clusterLoc, false);
        clusters[d] = cluster;
      }
    });

    groupControl.setValues(competitorsWithMarker, clustersCenter);
  }
  if (finishLineSet && refreshMeters) {
    rankControl.setValues(finishLineCrosses);
  }
}

function addRasterMapLayer(mapData, indexEventMap) {
  var bounds = ["topLeft", "topRight", "bottomRight", "bottomLeft"].map(
    function (corner) {
      var cornerCoords = mapData.coordinates[corner];
      return [cornerCoords.lat, cornerCoords.lon];
    }
  );
  var layer = L.tileLayer.wms(
    `${window.local.wmsServiceUrl}?v=${mapData.hash}`,
    {
      layers: `${window.local.eventId}/${indexEventMap + 1}`,
      bounds: bounds,
      tileSize: 512,
      noWrap: true,
      maxNativeZoom: mapData.max_zoom,
    }
  );
  layer.data = mapData;
  return layer;
}

function sortingFunction(a, b) {
  return a - b;
}

function fitInnerBounds(bounds) {
  var bLat = bounds.map((coord) => coord[0]).sort(sortingFunction);
  var bLon = bounds.map((coord) => coord[1]).sort(sortingFunction);
  var s = (bLat[0] + bLat[1]) / 2;
  var n = (bLat[2] + bLat[3]) / 2;
  var w = (bLon[0] + bLon[1]) / 2;
  var e = (bLon[2] + bLon[3]) / 2;
  var bounds1 = [
    [(n + s) / 2, w],
    [(n + s) / 2, e],
    [(n + s) / 2, e],
    [(n + s) / 2, w],
  ];
  var bounds2 = [
    [n, (e + w) / 2],
    [n, (e + w) / 2],
    [s, (e + w) / 2],
    [s, (e + w) / 2],
  ];
  var z1 = map.getBoundsZoom(bounds1);
  var z2 = map.getBoundsZoom(bounds2);
  if (z1 > z2) {
    map.fitBounds(bounds1, { animate: false });
  } else {
    map.fitBounds(bounds2, { animate: false });
  }
}

function setRasterMap(layer, fit) {
  layer.addTo(map);
  if (fit) {
    map.setBearing(layer.data.rotation, { animate: false });
    fitInnerBounds(layer.options.bounds);
  }
  layer.setOpacity(mapOpacity);
  rasterMap = layer;
}

function centerMap(e) {
  map.panTo(e.latlng);
}

function onPressCustomMassStart(e) {
  if (!isLiveMode) {
    isRealTime = false;
    isCustomStart = true;

    u("#real_time_button").removeClass("active");
    u("#mass_start_button").removeClass("active");
    setCustomStart(e.latlng);
    currentTime = getCompetitionStartDate() - getCompetitorsMaxDuration();
    prevShownTime = currentTime;
    if (!resetMassStartContextMenuItem) {
      resetMassStartContextMenuItem = map.contextmenu.insertItem(
        {
          text: banana.i18n("reset-mass-start"),
          callback: onPressResetMassStart,
        },
        2
      );
    }
  }
}

function onPressResetMassStart(e) {
  isRealTime = false;
  isCustomStart = false;

  currentTime = getCompetitionStartDate();
  prevShownTime = currentTime;

  if (resetMassStartContextMenuItem) {
    map.contextmenu.removeItem(resetMassStartContextMenuItem);
    resetMassStartContextMenuItem = null;
  }

  u("#real_time_button").removeClass("active");
  u("#mass_start_button").addClass("active");
}

function zoomIn(e) {
  map.zoomIn();
}

function zoomOut(e) {
  map.zoomOut();
}

function pressPlayPauseButton(e) {
  e.preventDefault();
  playbackPaused = !playbackPaused;
}

function onMoveProgressBar(perc) {
  if (isRealTime) {
    currentTime =
      getCompetitionStartDate() +
      (Math.min(clock.now(), getCompetitionEndDate()) -
        getCompetitionStartDate()) *
        perc;
  } else if (isCustomStart) {
    currentTime =
      getCompetitionStartDate() +
      getCompetitorsMinCustomOffset() +
      getCompetitorsMaxDuration(true) * perc;
  } else {
    currentTime =
      getCompetitionStartDate() + getCompetitorsMaxDuration() * perc;
  }
  prevShownTime = currentTime;
}

function pressProgressBar(e) {
  var perc =
    (e.pageX - document.getElementById("full_progress_bar").offsetLeft) /
    u("#full_progress_bar").size().width;
  onMoveProgressBar(perc);
}

function touchProgressBar(e) {
  var touchLocation = e.targetTouches[0];
  var perc =
    (touchLocation.pageX -
      document.getElementById("full_progress_bar").offsetLeft) /
    u("#full_progress_bar").size().width;
  e.preventDefault();
  onMoveProgressBar(perc);
}

function shareUrl(e) {
  e.preventDefault();
  var shareData = {
    title: u('meta[property="og:title"]').attr("content"),
    text: u('meta[property="og:description"]').attr("content"),
    url: qrUrl,
  };
  try {
    navigator
      .share(shareData)
      .then(function () {})
      .catch(function () {});
  } catch (err) {}
}

function updateText() {
  banana.setLocale(locale);
  var langFile = `${window.local.staticRoot}i18n/club/event/${locale}.json`;
  return fetch(`${langFile}?v=2023082700`)
    .then((response) => response.json())
    .then((messages) => {
      banana.load(messages, banana.locale);
    });
}
