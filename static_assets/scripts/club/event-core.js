var COLORS = [
  "#e6194B",
  "#3cb44b",
  "#4363d8",
  "#f58231",
  "#911eb4",
  "#42d4f4",
  "#f032e6",
  "#bfef45",
  "#469990",
  "#9A6324",
  "#800000",
  "#aaffc3",
  "#808000",
  "#000075",
  "#ffe119",
  "#a9a9a9",
  "#000000",
];
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
var showClusters = false;
var showControls = !(L.Browser.touch && L.Browser.mobile);
var colorModal = new bootstrap.Modal(document.getElementById("colorModal"));
var zoomOnRunners = false;
var clock = null;
var banana = null;
var sendInterval = 0;
var endEvent = null;
var startEvent = null;
var initialCompetitorDataLoaded = false;
var gpsEventSource = null;
var maxParticipantsDisplayed = 300;
var nbShown = 0;
var smoothFactor = 1;
var prevMapsJSONData = null;
var mapSelectorLayer = null;
var sidebarShown = true;
var isMapMoving = false;
var oldCrossingForNTimes = 1;
var intersectionCheckZoom = 18;
var supportedLanguages = {
  en: "English",
  es: "Español",
  fr: "Français",
  nl: "Nederlands",
  fi: "Suomi",
  sv: "Svenska",
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
      '<div class="m-0 py-0 px-3 fst-italic" style="color: red;text-shadow: -1px -1px 0 #fff,-1px 0px 0 #fff,-1px 1px 0 #fff,0px -1px 0 #fff,0px 0px 0 #fff,0px 1px 0 #fff,1px -1px 0 #fff,1px 0px 0 #fff,1px 1px 0 #fff">' +
      banana.i18n("live-mode") +
      '</div><div id="big-clock" class="py-0 px-3" style="color: #000;text-shadow: -1px -1px 0 #fff,-1px 0px 0 #fff,-1px 1px 0 #fff,0px -1px 0 #fff,0px 0px 0 #fff,0px 1px 0 #fff,1px -1px 0 #fff,1px 0px 0 #fff,1px 1px 0 #fff"></div>';
    u(this._div).css({
      display: "block",
      fontSize: "20px",
      color: "#fff",
      padding: "0",
      fontWeight: "bold",
      textTransform: "uppercase",
    });
  },
  setReplay() {
    this._div.innerHTML =
      '<div class="m-0 py-0 px-3" style="color: #666;text-shadow: -1px -1px 0 #fff,-1px 0px 0 #fff,-1px 1px 0 #fff,0px -1px 0 #fff,0px 0px 0 #fff,0px 1px 0 #fff,1px -1px 0 #fff,1px 0px 0 #fff,1px 1px 0 #fff">' +
      banana.i18n("replay-mode") +
      '</div><div id="big-clock" class="py-0 px-3" style="color: #000;text-shadow: -1px -1px 0 #fff,-1px 0px 0 #fff,-1px 1px 0 #fff,0px -1px 0 #fff,0px 0px 0 #fff,0px 1px 0 #fff,1px -1px 0 #fff,1px 0px 0 #fff,1px 1px 0 #fff""></div>';
    u(this._div).css({
      display: "block",
      fontSize: "20px",
      color: "#fff",
      padding: "0",
      fontWeight: "bold",
      textTransform: "uppercase",
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
  return yiq <= 168 ? "dark" : "light";
}

function getRunnerIcon(color, faded = false, focused = false) {
  var iconSize = 16;
  var liveColor = tinycolor(color).setAlpha(faded ? 0.4 : 0.75);
  var isDark = getContrastYIQ(color) === "dark";
  var svgRect = `<svg viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg"><circle fill="${liveColor.toRgbString()}" stroke="${
    isDark ? "white" : "black"
  }" stroke-width="${focused ? 3 : 1}px" cx="8" cy="8" r="6"/></svg>`;
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
  rightSide,
  faded = false,
  focused = false
) {
  var iconHtml =
    '<span style="opacity: ' +
    (faded ? 0.4 : 0.75) +
    ";color: " +
    color +
    '">' +
    u("<span/>").text(name).html() +
    "</span>";
  var iconClass =
    "runner-icon runner-icon-" +
    getContrastYIQ(color) +
    (focused ? " icon-focused" : "");
  var ic2 =
    iconClass +
    " leaflet-marker-icon leaflet-zoom-animated leaflet-interactive";
  var nameTagEl = document.createElement("div");
  nameTagEl.className = ic2;
  nameTagEl.innerHTML = iconHtml;
  var mapEl = document.getElementById("map");
  mapEl.appendChild(nameTagEl);
  var nameTagWidth = nameTagEl.childNodes[0].getBoundingClientRect().width;
  mapEl.removeChild(nameTagEl);
  var runnerIcon = L.divIcon({
    className: iconClass,
    html: iconHtml,
    iconAnchor: [rightSide ? nameTagWidth : 0, 0],
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

function appHeight() {
  const doc = document.documentElement;
  doc.style.setProperty("--app-height", `${window.innerHeight}px`);
  doc.style.setProperty(
    "--ctrl-height",
    `${document.getElementById("ctrl-wrapper").clientHeight}px`
  );
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
    setFinishLineContextMenuItem = map.contextmenu.insertItem(
      {
        text: banana.i18n("draw-finish-line"),
        callback: drawFinishLine,
      },
      1
    );
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
  map.contextmenu.removeItem(setFinishLineContextMenuItem);
  setFinishLineContextMenuItem = null;
  removeFinishLineContextMenuItem = map.contextmenu.insertItem(
    {
      text: banana.i18n("remove-finish-line"),
      callback: removeFinishLine,
    },
    1
  );
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
    map.invalidateSize();
    appHeight();
  });
}

function getCompetitionStartDate() {
  var res = +clock.now();
  competitorList.forEach(function (c) {
    var route = competitorRoutes[c.id];
    if (route) {
      res =
        res > route.getByIndex(0).timestamp
          ? route.getByIndex(0).timestamp
          : res;
    }
  });
  return res;
}

function getCompetitionEndDate() {
  var res = new Date(0);
  competitorList.forEach(function (c) {
    var route = competitorRoutes[c.id];
    if (route) {
      var idx = route.getPositionsCount() - 1;
      res =
        res < route.getByIndex(idx).timestamp
          ? route.getByIndex(idx).timestamp
          : res;
    }
  });
  return res;
}

function getCompetitorsMaxDuration(customOffset) {
  if (customOffset === undefined) {
    customOffset = false;
  }
  var res = 0;
  competitorList.forEach(function (c) {
    var route = competitorRoutes[c.id];
    if (route) {
      var idx = route.getPositionsCount() - 1;

      var dur =
        route.getByIndex(idx).timestamp -
        ((customOffset
          ? +new Date(c.custom_offset)
          : +new Date(c.start_time)) || getCompetitionStartDate());
      res = res < dur ? dur : res;
    }
  });
  return res;
}

function getCompetitorsMinCustomOffset() {
  var res = 0;
  competitorList.forEach(function (c) {
    var route = competitorRoutes[c.id];
    if (route) {
      var off = c.custom_offset - c.start_time || 0;
      res = res < off ? off : res;
    }
  });
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
  u("#live_button").addClass("active");
  u("#replay_button").removeClass("active");
  u("#real_time_button").removeClass("active");
  u("#mass_start_button").removeClass("active");
  u("#replay_mode_buttons").hide();
  u("#replay_control_buttons").hide();
  appHeight();

  isLiveMode = true;
  isRealTime = true;
  function whileLive(ts) {
    if (
      ts - routesLastFetched > fetchPositionInterval * 1e3 &&
      !isCurrentlyFetchingRoutes
    ) {
      if (!window.local.noDelay) {
        fetchCompetitorRoutes();
      }
    }
    currentTime =
      +clock.now() - (fetchPositionInterval + 5 + sendInterval) * 1e3; // Delay by the fetch interval (10s) + the cache interval (5sec) + the send interval (default 5sec)
    if (window.local.noDelay) {
      currentTime = +clock.now();
    }
    if (ts - prevDisplayRefresh > 100) {
      drawCompetitors();
      prevDisplayRefresh = ts;
    }
    var isStillLive = endEvent >= clock.now();
    if (!isStillLive) {
      u("#live_button").hide();
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
  if (!isLiveMode && u("#replay_button").hasClass("active")) {
    return;
  }

  u(".if-live").addClass("d-none");
  u("#full_progress_bar").removeClass("d-none");
  u("#real_time_button").addClass("active");
  u("#mass_start_button").removeClass("active");

  eventStateControl.setReplay();
  u("#live_button").removeClass("active");
  u("#replay_button").addClass("active");
  u("#replay_mode_buttons").css({ display: "" });
  u("#replay_control_buttons").css({ display: "" });
  appHeight();

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
  prevShownTime = getCompetitionStartDate();
  playbackRate = 8;
  function whileReplay(ts) {
    if (
      isLiveEvent &&
      ts - routesLastFetched > fetchPositionInterval * 1e3 &&
      !isCurrentlyFetchingRoutes
    ) {
      if (!window.local.noDelay) {
        fetchCompetitorRoutes();
      }
    }
    var actualPlaybackRate = playbackPaused ? 0 : playbackRate;

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
    if (currentTime > liveTime) {
      selectLiveMode();
      return;
    }

    if (ts - prevDisplayRefresh > 100) {
      drawCompetitors();
      prevDisplayRefresh = ts;
      prevShownTime = currentTime;
    }

    var isStillLive = isLiveEvent && endEvent >= clock.now();
    var isBackLive = !isLiveEvent && endEvent >= clock.now();
    if (!isStillLive) {
      u("#live_button").hide();
      isLiveEvent = false;
    }
    if (isBackLive) {
      u("#live_button").show();
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
  var data = {
    lastDataTs:
      Math.round(lastDataTs / fetchPositionInterval) * fetchPositionInterval,
  };
  reqwest({
    url: url,
    data: data,
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
      if (!initialCompetitorDataLoaded && window.local.noDelay) {
        initialCompetitorDataLoaded = true;
        connectToGpsEvents();
      }
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
    data: { t: +new Date() },
    withCredentials: true,
    crossOrigin: true,
    type: "json",
    success: function (response) {
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
        var currentMapNewData = response.maps.find(function (m) {
          return (
            rasterMap &&
            m.id === rasterMap.data.id &&
            m.modification_date !== rasterMap.data.modification_date
          );
        });
        var currentMapStillExists = response.maps.find(function (m) {
          return rasterMap && m.id === rasterMap.data.id;
        });
        if (rasterMap && (currentMapNewData || response.maps.length === 0)) {
          rasterMap.remove();
        }
        if (mapSelectorLayer) {
          mapSelectorLayer.remove();
        }
        if (response.maps.length) {
          var mapChoices = {};
          for (var i = 0; i < response.maps.length; i++) {
            var m = response.maps[i];
            if (
              (currentMapStillExists && m.id === currentMapStillExists.id) ||
              (!currentMapStillExists && m.default)
            ) {
              m.title =
                !m.title && m.default
                  ? '<i class="fa-solid fa-star"></i> Main Map'
                  : u("<span/>").text(m.title).html();
              var bounds = [
                [m.coordinates.topLeft.lat, m.coordinates.topLeft.lon],
                [m.coordinates.topRight.lat, m.coordinates.topRight.lon],
                [m.coordinates.bottomRight.lat, m.coordinates.bottomRight.lon],
                [m.coordinates.bottomLeft.lat, m.coordinates.bottomLeft.lon],
              ];
              rasterMap = addRasterMap(
                bounds,
                m.hash,
                m.max_zoom,
                currentMapNewData,
                i,
                m
              );
              mapChoices[m.title] = rasterMap;
            } else {
              m.title =
                !m.title && m.default
                  ? '<i class="fa-solid fa-star"></i> Main Map'
                  : u("<span/>").text(m.title).html();
              var bounds = [
                [m.coordinates.topLeft.lat, m.coordinates.topLeft.lon],
                [m.coordinates.topRight.lat, m.coordinates.topRight.lon],
                [m.coordinates.bottomRight.lat, m.coordinates.bottomRight.lon],
                [m.coordinates.bottomLeft.lat, m.coordinates.bottomLeft.lon],
              ];
              mapChoices[m.title] = L.tileLayer.wms(
                window.local.wmsServiceUrl + "?v=" + m.hash,
                {
                  layers: window.local.eventId + "/" + i,
                  bounds: bounds,
                  tileSize: 512,
                  noWrap: true,
                  className: "wms512",
                  maxNativeZoom: m.max_zoom,
                }
              );
              mapChoices[m.title].data = m;
            }
          }
          if (response.maps.length > 1) {
            mapSelectorLayer = L.control.layers(mapChoices, null, {
              collapsed: false,
            });
            try {
              mapSelectorLayer.addTo(map);
            } catch (e) {}
          }
        }
      }
    },
  });
}

function updateCompetitorList(newList) {
  newList.forEach(updateCompetitor);
}

function setCustomStart(latlng) {
  competitorList.forEach(function (c) {
    var minDist = Infinity;
    var minDistT = null;
    var route = competitorRoutes[c.id];
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
      c.custom_offset = minDistT;
    }
  });
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
  try {
    map.invalidateSize();
  } catch {}
}

function showSidebar() {
  u("#map")
    .addClass("col-12")
    .addClass("col-sm-7")
    .addClass("col-lg-9")
    .addClass("col-xxl-10");
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
  }
}

function toggleFullCompetitor(c) {
  if (!c.isShown) {
    return;
  }
  if (c.displayFullRoute) {
    c.displayFullRoute = null;
    u("#fullRouteIcon-" + c.id).attr({ fill: null });
  } else {
    c.displayFullRoute = true;
    u("#fullRouteIcon-" + c.id).attr({ fill: "#20c997" });
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

function toggleFocusCompetitor(c) {
  const wasFocused = c.focused;
  competitorList.map((comp) => {
    if (comp.focused) {
      comp.focused = false;
      u("#focusedIcon-" + comp.id).removeClass("route-focused");
    }
  });
  if (wasFocused) {
    c.focused = false;
    u("#focusedIcon-" + c.id).removeClass("route-focused");
  } else {
    if (!c.isShown) {
      return;
    }
    c.focused = true;
    u("#focusedIcon-" + c.id).addClass("route-focused");
    zoomOnCompetitor(c);
  }
}

function toggleHighlightCompetitor(c) {
  const wasHighlighted = c.highlighted;
  if (wasHighlighted) {
    c.highlighted = false;
    u("#highlightIcon-" + c.id).removeClass("competitor-highlighted");
  } else {
    if (!c.isShown) {
      return;
    }
    c.highlighted = true;
    u("#highlightIcon-" + c.id).addClass("competitor-highlighted");
    console.log("ddd");
  }
  if (c.nameMarker) {
    c.nameMarker.remove();
    c.nameMarker = null;
  }
  if (c.mapMarker) {
    c.mapMarker.remove();
    c.mapMarker = null;
  }
  if (c.tail) {
    c.tail.remove();
    c.tail = null;
  }
}

function displayCompetitorList(force) {
  if (!force && optionDisplayed) {
    return;
  }
  optionDisplayed = false;
  var scrollTopDiv = u("#listCompetitor").nodes?.[0]?.scrollTop;
  var listDiv = u(
    '<div id="listCompetitor" style="overflow-y:auto;" class="mt-1"/>'
  );
  nbShown = 0;
  competitorList.forEach(function (competitor, ii) {
    competitor.color = competitor.color || getColor(ii);

    competitor.isShown =
      typeof competitor.isShown === "undefined"
        ? nbShown < maxParticipantsDisplayed
        : competitor.isShown;
    nbShown += competitor.isShown ? 1 : 0;
    var div = u('<div class="card-body px-1 pt-1 pb-0"/>');
    div.html(
      '<div class="float-start color-tag me-1" style="cursor: pointer"><i class="media-object fa-solid fa-circle fa-3x icon-sidebar" style="font-size: 1em;color:' +
        competitor.color +
        '"></i></div>\
        <div><div class="text-nowrap overflow-hidden ps-0 text-truncate"><b>' +
        u("<div/>").text(competitor.name).html() +
        '</b></div>\
        <div class="text-nowrap text-truncate overflow-hidden ps-0 ' +
        (competitor.isShown ? "route-displayed" : "route-not-displayed") +
        '">' +
        // toggle on off
        '<div class="form-check form-switch d-inline-block align-middle" style="margin-right:-5px;padding-top: 2px" data-bs-toggle="tooltip" data-bs-title="' +
        banana.i18n("toggle") +
        '"><input class="form-check-input competitor-switch" type="checkbox" id="switch-competitor-' +
        competitor.id +
        '"' +
        (competitor.isShown ? " checked" : "") +
        "></div>" +
        // center on competitor
        '<button type="button" class="center_competitor_btn btn btn-default btn-sm p-0 ms-1 me-0" aria-label="focus" data-bs-toggle="tooltip" data-bs-title="' +
        banana.i18n("center") +
        '"><i class="fa-solid fa-location-dot"></i></button>' +
        // toggle follow competitor
        '<button type="button" class="focus_competitor_btn btn btn-default btn-sm p-0 ms-1 me-0" aria-label="focus on competitor" data-bs-toggle="tooltip" data-bs-title="' +
        banana.i18n("follow") +
        '">' +
        '<i class="fa-solid fa-crosshairs' +
        (competitor.focused ? " route-focused" : "") +
        '" id="focusedIcon-' +
        competitor.id +
        '"></i></button>' +
        // toggle highligh competitor
        '<button type="button" class="highlight_competitor_btn btn btn-default btn-sm p-0 ms-1 me-0" aria-label="highlight competitor" data-bs-toggle="tooltip" data-bs-title="' +
        banana.i18n("highlight") +
        '">' +
        '<i class="fa-solid fa-highlighter' +
        (competitor.highlighted ? " competitor-highlighted" : "") +
        '" id="highlightIcon-' +
        competitor.id +
        '"></i></button>' +
        // toggle full route
        '<button type="button" class="full_competitor_btn btn btn-default btn-sm p-0 ms-1 me-0" aria-label="full route" data-bs-toggle="tooltip" data-bs-title="' +
        banana.i18n("full-route") +
        '"><svg id="fullRouteIcon-' +
        competitor.id +
        '" ' +
        (competitor.isShown
          ? competitor.displayFullRoute
            ? 'fill="#20c997"'
            : ""
          : 'fill="#aaa"') +
        ' viewBox="0 0 48 48" width="19px"><path d="M28.65 42.95q-2.85 0-4.775-2.075Q21.95 38.8 21.95 35.45q0-2.5 1.325-4.4 1.325-1.9 3.125-3.1 1.8-1.2 3.7-1.825 1.9-.625 3.2-.675-.15-2.4-1.1-3.475-.95-1.075-2.75-1.075-2 0-3.7 1.15-1.7 1.15-4.5 5.1-2.85 4.05-5.075 5.65-2.225 1.6-4.675 1.6-2.5 0-4.475-1.625Q5.05 31.15 5.05 27.15q0-1.45 1.025-3.7T9.65 17.2q1.9-2.55 2.5-3.725.6-1.175.6-2.175 0-.55-.325-.875-.325-.325-.925-.325-.3 0-.8.15t-1 .6q-1 .55-1.825.525-.825-.025-1.375-.625-.7-.55-.7-1.525 0-.975.7-1.625 1.15-1 2.475-1.55Q10.3 5.5 11.75 5.5q2.35 0 3.9 1.65Q17.2 8.8 17.2 11q0 2.25-.95 4.15-.95 1.9-3.2 5.15-2.25 3.4-2.875 4.625T9.55 27.45q0 1.35.775 1.775.775.425 1.625.425 1.2 0 2.4-1.125t3.55-4.275q3.35-4.4 6-6.175 2.65-1.775 5.95-1.775 3.15 0 5.425 2.275T37.85 25.3h2.9q1 0 1.625.625T43 27.5q0 1-.625 1.65-.625.65-1.625.65h-2.9q-.55 8.8-3.9 10.975-3.35 2.175-5.3 2.175Zm.15-4.65q1.05 0 2.6-1.525t1.95-6.725q-1.9.2-4.375 1.55T26.5 35.95q0 1.1.575 1.725t1.725.625Z"/>' +
        "</svg></button>" +
        (competitorBatteyLevels.hasOwnProperty(competitor.id)
          ? '<div class="float-end d-inline-block text-end if-live' +
            (isLiveMode ? "" : " d-none") +
            '">' +
            '<span style="color: ' +
            (competitorBatteyLevels[competitor.id] !== null
              ? "grey"
              : "lightgrey") +
            '; cursor: pointer" class="battery_level" data-bs-toggle="tooltip" data-bs-title="' +
            (competitorBatteyLevels[competitor.id] !== null
              ? competitorBatteyLevels[competitor.id] + "%"
              : "unknown") +
            '"><i class="fa-solid fa-battery-' +
            batteryIconName(competitorBatteyLevels[competitor.id]) +
            ' fa-rotate-270"></i></span></div>'
          : "") +
        '<div class="float-end d-inline-block text-end" style="line-height:10px;"><span class="speedometer"></span><br/><span class="odometer"></span></div>' +
        "</div>"
    );
    var diva = u(
      '<div class="card mb-1" style="background-color:transparent";/>'
    ).append(div);
    u(div)
      .find(".color-tag")
      .on("click", function () {
        u("#colorModalLabel").text(
          banana.i18n("select-color-for", competitor.name)
        );
        var color = competitor.color;
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
          colorModal.hide();
          displayCompetitorList();

          if (competitor.mapMarker) {
            map.removeLayer(competitor.mapMarker);
          }
          if (competitor.nameMarker) {
            map.removeLayer(competitor.nameMarker);
          }
          if (competitor.tail) {
            map.removeLayer(competitor.tail);
          }
          competitor.mapMarker = null;
          competitor.nameMarker = null;
          competitor.tail = null;

          u("#save-color").off("click");
        });
      });
    u(div)
      .find(".competitor-switch")
      .on("click", function (e) {
        if (!e.target.checked) {
          competitor.isShown = false;
          competitor.focused = false;
          competitor.highlighted = false;
          u("#focusedIcon-" + competitor.id).removeClass("route-focused");
          competitor.displayFullRoute = null;
          u("#fullRouteIcon-" + competitor.id).attr({ fill: "#aaa" });
          u(e.target)
            .parent()
            .parent()
            .removeClass("route-displayed")
            .addClass("route-not-displayed");
          if (competitor.mapMarker) {
            map.removeLayer(competitor.mapMarker);
          }
          if (competitor.nameMarker) {
            map.removeLayer(competitor.nameMarker);
          }
          if (competitor.tail) {
            map.removeLayer(competitor.tail);
          }
          competitor.mapMarker = null;
          competitor.nameMarker = null;
          competitor.tail = null;
          u(e.target).parent().parent().find(".speedometer").text("");
          u(e.target).parent().parent().find(".odometer").text("");
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
          u(e.target)
            .parent()
            .parent()
            .removeClass("route-not-displayed")
            .addClass("route-displayed");

          u("#fullRouteIcon-" + competitor.id).attr({ fill: null });
          updateCompetitor(competitor);
          nbShown += 1;
        }
      });
    u(div)
      .find(".center_competitor_btn")
      .on("click", function () {
        zoomOnCompetitor(competitor);
      });
    u(div)
      .find(".full_competitor_btn")
      .on("click", function () {
        toggleFullCompetitor(competitor);
      });
    u(div)
      .find(".focus_competitor_btn")
      .on("click", function () {
        toggleFocusCompetitor(competitor);
      });
    u(div)
      .find(".highlight_competitor_btn")
      .on("click", function () {
        toggleHighlightCompetitor(competitor);
      });
    if (
      searchText === null ||
      searchText === "" ||
      competitor.name.toLowerCase().search(searchText) != -1
    ) {
      listDiv.append(diva);
    }
    competitor.div = div;
    competitor.speedometer = div.find(".speedometer");
    competitor.odometer = div.find(".odometer");
  });
  if (competitorList.length === 0) {
    var div = u('<div class="text-center"/>');
    var txt = banana.i18n("no-competitors");
    div.html("<h3>" + txt + "</h3>");
    listDiv.append(div);
  }
  if (!searchText) {
    var mainDiv = u('<div id="competitorSidebar" class="d-flex flex-column"/>');
    var topDiv = u("<div/>");
    topDiv.append(
      u('<div class="text-end mb-0"/>').append(
        u('<button class="btn btn-default btn-sm" aria-label="close"/>')
          .html('<i class="fa-solid fa-xmark"></i>')
          .on("click", toggleCompetitorList)
      )
    );
    if (competitorList.length) {
      var hideAllTxt = banana.i18n("hide-all");
      var showAllTxt = banana.i18n("show-all");
      topDiv.append(
        '<div class="text-center text-nowrap">' +
          '<button id="showAllCompetitorBtn" class="btn btn-default"><i class="fa-solid fa-eye"></i> ' +
          showAllTxt +
          "</button>" +
          '<button id="hideAllCompetitorBtn" class="btn btn-default"><i class="fa-solid fa-eye-slash"></i> ' +
          hideAllTxt +
          "</button>" +
          "</div>"
      );
    }
    u(topDiv)
      .find("#hideAllCompetitorBtn")
      .on("click", function () {
        competitorList.forEach(function (competitor) {
          competitor.isShown = false;
          competitor.focused = false;
          competitor.highlighted = false;
          competitor.displayFullRoute = false;

          if (competitor.mapMarker) {
            map.removeLayer(competitor.mapMarker);
          }
          if (competitor.nameMarker) {
            map.removeLayer(competitor.nameMarker);
          }
          if (competitor.tail) {
            map.removeLayer(competitor.tail);
          }
          competitor.mapMarker = null;
          competitor.nameMarker = null;
          competitor.tail = null;
          updateCompetitor(competitor);
          nbShown = 0;
        });
        displayCompetitorList();
      });
    u(topDiv)
      .find("#showAllCompetitorBtn")
      .on("click", function () {
        nbShown = competitorList.reduce(function (a, v) {
          return v.isShown ? a + 1 : a;
        }, 0);
        var didNotShowAll = false;
        competitorList.forEach(function (competitor, idx) {
          if (nbShown >= maxParticipantsDisplayed && !competitor.isShown) {
            didNotShowAll = true;
          } else if (!competitor.isShown) {
            nbShown += 1;
            competitor.isShown = true;
          }
          updateCompetitor(competitor);
        });
        if (didNotShowAll) {
          swal({
            title: banana.i18n("reached-max-runners", maxParticipantsDisplayed),
            type: "warning",
            confirmButtonText: "OK",
          });
        }
        displayCompetitorList();
      });
    if (competitorList.length > 10) {
      topDiv.append(
        u('<input class="form-control" type="search" val=""/>')
          .on("input", filterCompetitorList)
          .attr("placeholder", banana.i18n("search-competitors"))
      );
    }
    mainDiv.append(topDiv);
    mainDiv.append(listDiv);
    u("#sidebar").html("");
    u("#sidebar").append(mainDiv);
  } else {
    u("#listCompetitor").remove();
    var mainDiv = u("#competitorSidebar");
    mainDiv.append(listDiv);
  }
  if (competitorList.length > 10) {
    listDiv.addClass("with_search_bar");
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
  optionDisplayed = true;
  searchText = null;
  var mainDiv = u("<div/>");
  mainDiv.append(
    u('<div class="text-end mb-0"/>').append(
      u('<button class="btn btn-default btn-sm" aria-label="close"/>')
        .html('<i class="fa-solid fa-xmark"></i>')
        .on("click", displayOptions)
    )
  );
  var qrDataUrl = null;
  if (qrUrl) {
    var qr = new QRious();
    qr.set({
      background: "#f5f5f5",
      foreground: "black",
      level: "L",
      value: qrUrl,
      size: 138,
    });
    qrDataUrl = qr.toDataURL();
  }
  mainDiv.append(
    u(
      '<div id="listOptions" style="overflow-y:auto;overflow-x: hidden;" />'
    ).html(
      '<div class="mb-2"><h4>' +
        banana.i18n("tails") +
        "</h4>" +
        '<div class="form-group">' +
        '<label for="tailLengthInput">' +
        banana.i18n("length-in-seconds") +
        "</label>" +
        '<div class="row g-3">' +
        '<div class="col-auto"><input type="number" min="0" max="9999" class="form-control tailLengthControl" id="tailLengthHoursInput" value="' +
        Math.floor(tailLength / 3600) +
        '" style="width:100px"/></div><div class="col-auto" style="vertical-align: bottom;margin:1.3em -.7em">:</div>' +
        '<div class="col-auto"><input type="number" min="0" max="59" class="form-control tailLengthControl" id="tailLengthMinutesInput" value="' +
        (Math.floor(tailLength / 60) % 60) +
        '" style="width:70px"/></div><div class="col-auto" style="vertical-align: top;margin:1.3em -.7em">:</div>' +
        '<div class="col-auto"><input type="number" min="0" max="59" class="form-control tailLengthControl" id="tailLengthSecondsInput" value="' +
        (tailLength % 60) +
        '"style="width:70px" /></div>' +
        "</div>" +
        "</div>" +
        '</div><div class="mb-2"><h4>' +
        banana.i18n("map-controls") +
        "</h4>" +
        '<div class="form-check form-switch d-inline-block ms-1"><input class="form-check-input" type="checkbox" id="toggle-controls-switch"' +
        (showControls ? " checked" : "") +
        '><label class="form-check-label" for="toggle-controls-switch">' +
        banana.i18n("show-map-controls") +
        "</label></div>" +
        '</div><div class="mb-2"><h4>' +
        banana.i18n("groupings") +
        "</h4>" +
        '<div class="form-check form-switch d-inline-block ms-1"><input class="form-check-input" type="checkbox" id="toggle-clusters-switch"' +
        (showClusters ? " checked" : "") +
        '><label class="form-check-label" for="toggle-clusters-switch">' +
        banana.i18n("show-groupings") +
        "</label></div>" +
        '</div><div class="mb-2"><h4 class="text-nowrap">' +
        '<i class="fa-solid fa-language"></i> ' +
        banana.i18n("language") +
        "</h4>" +
        '<select class="form-select" id="languageSelector">' +
        Object.keys(supportedLanguages)
          .map(function (l) {
            return (
              '<option value="' +
              l +
              '"' +
              (locale === l ? " selected" : "") +
              ">" +
              supportedLanguages[l] +
              "</option>"
            );
          })
          .join("") +
        "</select>" +
        (qrUrl
          ? `<h4>${banana.i18n("qr-link")}</h4>
<p class="text-center">
<img class="p-2" src="${qrDataUrl}" alt="qr"><br/>
<a class="small fw-bold" href="${qrUrl}">${qrUrl.replace(
              /^https?:\/\//,
              ""
            )}</a>
</p>`
          : "")
    )
  );
  u(mainDiv)
    .find("#languageSelector")
    .on("change", function (e) {
      window.localStorage.setItem("lang", e.target.value);
      window.location.search = `lang=${e.target.value}`;
    });
  u(mainDiv)
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
      u("#tailLengthHoursInput").val(Math.floor(tailLength / 3600));
      u("#tailLengthMinutesInput").val(Math.floor((tailLength / 60) % 60));
      u("#tailLengthSecondsInput").val(Math.floor(tailLength % 60));
    });
  u(mainDiv)
    .find("#toggle-controls-switch")
    .on("click", function (e) {
      if (!e.target.checked) {
        showControls = false;
        map.removeControl(panControl);
        map.removeControl(zoomControl);
        map.removeControl(rotateControl);
      } else {
        map.addControl(panControl);
        map.addControl(zoomControl);
        map.addControl(rotateControl);
        showControls = true;
      }
    });
  u(mainDiv)
    .find("#toggle-clusters-switch")
    .on("click", function (e) {
      if (!e.target.checked) {
        showClusters = false;
        map.removeControl(groupControl);
        for (var [key, c] of Object.entries(clusters)) {
          if (c.mapMarker) {
            map.removeLayer(c.mapMarker);
            clusters[key].mapMarker = null;
          }
          if (c.nameMarker) {
            map.removeLayer(c.nameMarker);
            clusters[key].nameMarker = null;
          }
        }
        clusters = {};
      } else {
        groupControl = L.control.grouping({ position: "topright" });
        map.addControl(groupControl);
        showClusters = true;
      }
    });
  u("#sidebar").html("");
  u("#sidebar").append(mainDiv);
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

function getProgressBarText(currentTime, bg = false) {
  var result = "";
  var viewedTime = currentTime;
  if (!isRealTime) {
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
    if (
      dayjs(getCompetitionStartDate()).format("YYYY-MM-DD") !==
        dayjs(getCompetitionEndDate()).format("YYYY-MM-DD") &&
      !isLiveMode
    ) {
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

function checkVisible(elm) {
  var rect = elm.getBoundingClientRect();
  var viewHeight = Math.max(
    document.documentElement.clientHeight,
    window.innerHeight
  );
  return !(rect.bottom < 0 || rect.top - viewHeight >= 0);
}

function drawCompetitors() {
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
  appHeight();
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
  }
  u("#progress_bar")
    .css({ width: perc + "%" })
    .attr("aria-valuenow", perc);
  u("#progress_bar_text").text(getProgressBarText(currentTime));
  u("#big-clock").html(getProgressBarText(currentTime, true));

  if (isMapMoving) return;

  var oldFinishCrosses = finishLineCrosses.slice();
  finishLineCrosses = [];
  competitorList.forEach(function (competitor) {
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
      }
      if (
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
                    new Date(competitor.start_time) - getCompetitionStartDate();
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
                  L.latLng([tPoint.coords.latitude, tPoint.coords.longitude]),
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
                    new Date(competitor.start_time) - getCompetitionStartDate();
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
      var hasPointLast30sec = route.hasPointInInterval(
        viewedTime - 30 * 1e3,
        viewedTime
      );
      var loc = route.getByTime(viewedTime);

      if (competitor.focused) {
        const mapSize = map.getSize();
        const placeXY = map.latLngToContainerPoint([
          loc.coords.latitude,
          loc.coords.longitude,
        ]);
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

      if (viewedTime < route.getByIndex(0).timestamp) {
        ["mapMarker", "nameMarker", "tail"].forEach(function (layerName) {
          if (competitor[layerName]) {
            map.removeLayer(competitor[layerName]);
          }
          competitor[layerName] = null;
        });
      }

      if (viewedTime >= route.getByIndex(0).timestamp && !hasPointLast30sec) {
        if (!competitor.idle) {
          ["mapMarker", "nameMarker", "tail"].forEach(function (layerName) {
            if (competitor[layerName]) {
              map.removeLayer(competitor[layerName]);
            }
            competitor[layerName] = null;
          });
          competitor.idle = true;
        }
        if (loc && !isNaN(loc.coords.latitude)) {
          if (competitor.mapMarker == undefined) {
            var idleColor = tinycolor(competitor.color).setAlpha(0.4);
            var svgRect = `<svg viewBox="0 0 8 8" xmlns="http://www.w3.org/2000/svg"><circle fill="${idleColor.toRgbString()}" cx="4" cy="4" r="3"/></svg>`;
            var pulseIcon = L.icon({
              iconUrl: encodeURI("data:image/svg+xml," + svgRect),
              iconSize: [8, 8],
              shadowSize: [8, 8],
              iconAnchor: [4, 4],
              shadowAnchor: [0, 0],
              popupAnchor: [0, 0],
            });
            competitor.mapMarker = L.marker(
              [loc.coords.latitude, loc.coords.longitude],
              { icon: pulseIcon }
            );
            competitor.mapMarker.addTo(map);
          } else {
            competitor.mapMarker.setLatLng([
              loc.coords.latitude,
              loc.coords.longitude,
            ]);
          }
          var pointX = map.latLngToContainerPoint([
            loc.coords.latitude,
            loc.coords.longitude,
          ]).x;
          var mapMiddleX = map.getSize().x / 2;
          if (
            pointX > mapMiddleX &&
            !competitor.isNameOnRight &&
            competitor.nameMarker
          ) {
            map.removeLayer(competitor.nameMarker);
            competitor.nameMarker = null;
          } else if (
            pointX <= mapMiddleX &&
            competitor.isNameOnRight &&
            competitor.nameMarker
          ) {
            map.removeLayer(competitor.nameMarker);
            competitor.nameMarker = null;
          }
          if (competitor.nameMarker == undefined) {
            var isOnRight = pointX > mapMiddleX;
            competitor.isNameOnRight = isOnRight;
            var runnerIcon = getRunnerNameMarker(
              competitor.short_name,
              competitor.color,
              isOnRight,
              true,
              competitor.highlighted
            );
            competitor.nameMarker = L.marker(
              [loc.coords.latitude, loc.coords.longitude],
              { icon: runnerIcon }
            );
            competitor.nameMarker.addTo(map);
          } else {
            competitor.nameMarker.setLatLng([
              loc.coords.latitude,
              loc.coords.longitude,
            ]);
          }
        }
      } else if (competitor.idle) {
        ["mapMarker", "nameMarker", "tail"].forEach(function (layerName) {
          if (competitor[layerName]) {
            map.removeLayer(competitor[layerName]);
          }
          competitor[layerName] = null;
        });
        competitor.idle = false;
      }

      if (loc && !isNaN(loc.coords.latitude) && hasPointLast30sec) {
        if (!competitor.mapMarker) {
          var runnerIcon = getRunnerIcon(
            competitor.color,
            false,
            competitor.highlighted
          );
          competitor.mapMarker = L.marker(
            [loc.coords.latitude, loc.coords.longitude],
            { icon: runnerIcon }
          );
          competitor.mapMarker.addTo(map);
        } else {
          competitor.mapMarker.setLatLng([
            loc.coords.latitude,
            loc.coords.longitude,
          ]);
        }
        var pointX = map.latLngToContainerPoint([
          loc.coords.latitude,
          loc.coords.longitude,
        ]).x;
        var mapMiddleX = map.getSize().x / 2;
        if (
          pointX > mapMiddleX &&
          !competitor.isNameOnRight &&
          competitor.nameMarker
        ) {
          map.removeLayer(competitor.nameMarker);
          competitor.nameMarker = null;
        } else if (
          pointX <= mapMiddleX &&
          competitor.isNameOnRight &&
          competitor.nameMarker
        ) {
          map.removeLayer(competitor.nameMarker);
          competitor.nameMarker = null;
        }
        if (competitor.nameMarker == undefined) {
          var isNameOnRight = pointX > mapMiddleX;
          var runnerIcon = getRunnerNameMarker(
            competitor.short_name,
            competitor.color,
            isNameOnRight,
            false,
            competitor.highlighted
          );
          competitor.isNameOnRight = isNameOnRight;
          competitor.nameMarker = L.marker(
            [loc.coords.latitude, loc.coords.longitude],
            { icon: runnerIcon }
          );
          competitor.nameMarker.addTo(map);
        } else {
          competitor.nameMarker.setLatLng([
            loc.coords.latitude,
            loc.coords.longitude,
          ]);
        }
      }
      var tail = null;
      var hasPointInTail = false;
      if (competitor.displayFullRoute) {
        tail = route.extractInterval(-Infinity, viewedTime);
        hasPointInTail = route.hasPointInInterval(-Infinity, viewedTime);
      } else {
        tail = route.extractInterval(viewedTime - tailLength * 1e3, viewedTime);
        hasPointInTail = route.hasPointInInterval(
          viewedTime - tailLength * 1e3,
          viewedTime
        );
      }
      if (!hasPointInTail) {
        if (competitor.tail) {
          map.removeLayer(competitor.tail);
        }
        competitor.tail = null;
      } else {
        var tailLatLng = [];
        tail.getArray().forEach(function (pos) {
          if (!isNaN(pos.coords.latitude)) {
            tailLatLng.push([pos.coords.latitude, pos.coords.longitude]);
          }
        });
        if (competitor.tail == undefined) {
          competitor.tail = L.polyline(tailLatLng, {
            color: competitor.color,
            opacity: 0.75,
            weight: 5,
            smoothFactor: smoothFactor,
            className: competitor.focused ? "icon-focused" : "",
          }).addTo(map);
        } else {
          competitor.tail.setLatLngs(tailLatLng);
        }
      }
      var tail30s = route.extractInterval(viewedTime - 30 * 1e3, viewedTime);
      var hasPointInTail = route.hasPointInInterval(
        viewedTime - 30 * 1e3,
        viewedTime
      );
      if (!hasPointInTail) {
        competitor.speedometer.text("--'--\"/km");
      } else {
        if (checkVisible(competitor.speedometer.nodes[0])) {
          var distance = 0;
          var prevPos = null;
          tail30s.getArray().forEach(function (pos) {
            if (prevPos && !isNaN(pos.coords.latitude)) {
              distance += pos.distance(prevPos);
            }
            prevPos = pos;
          });
          var speed = (30 / distance) * 1000;
          competitor.speedometer.text(formatSpeed(speed));
        }
      }
      if (checkVisible(competitor.odometer.nodes[0])) {
        var totalDistance = route.distanceUntil(viewedTime);
        competitor.odometer.text((totalDistance / 1000).toFixed(1) + "km");
      }
    }
  });

  // Create cluster
  if (showClusters) {
    var listCompWithMarker = [];
    var gpsPointData = [];
    competitorList.forEach(function (competitor) {
      if (competitor.mapMarker) {
        listCompWithMarker.push(competitor);
        var latLon = competitor.mapMarker.getLatLng();
        gpsPointData.push({
          location: {
            accuracy: 0,
            latitude: latLon.lat,
            longitude: latLon.lng,
          },
        });
      }
    });
    var dbscanner = jDBSCAN()
      .eps(0.015)
      .minPts(1)
      .distance("HAVERSINE")
      .data(gpsPointData);
    var gpsPointAssignmentResult = dbscanner();
    var clusterCenters = dbscanner.getClusters();

    Object.keys(clusters).forEach(function (k) {
      if (gpsPointAssignmentResult.indexOf(k) === -1) {
        if (clusters[k].mapMarker) {
          map.removeLayer(clusters[k].mapMarker);
          clusters[k].mapMarker = null;
        }
        if (clusters[k].nameMarker) {
          map.removeLayer(clusters[k].nameMarker);
          clusters[k].nameMarker = null;
        }
      }
    });

    gpsPointAssignmentResult.forEach(function (d, i) {
      if (d != 0) {
        var cluster = clusters[d] || {};
        var clusterCenter = clusterCenters[d - 1];
        if (!cluster.color) {
          cluster.color = getColor(i);
        }
        var competitorInCluster = listCompWithMarker[i];
        ["mapMarker", "nameMarker"].forEach(function (layerName) {
          if (competitorInCluster[layerName]) {
            map.removeLayer(competitorInCluster[layerName]);
          }
          competitorInCluster[layerName] = null;
        });
        if (cluster.mapMarker) {
          cluster.mapMarker.setLatLng([
            clusterCenter.location.latitude,
            clusterCenter.location.longitude,
          ]);
        } else {
          var runnerIcon = getRunnerIcon(cluster.color);
          cluster.mapMarker = L.marker(
            [clusterCenter.location.latitude, clusterCenter.location.longitude],
            { icon: runnerIcon }
          );
          cluster.mapMarker.addTo(map);
        }

        var pointX = map.latLngToContainerPoint([
          clusterCenter.location.latitude,
          clusterCenter.location.longitude,
        ]).x;
        var mapMiddleX = map.getSize().x / 2;
        if (
          pointX > mapMiddleX &&
          !cluster.isNameOnRight &&
          cluster.nameMarker
        ) {
          map.removeLayer(cluster.nameMarker);
          cluster.nameMarker = null;
        } else if (
          pointX <= mapMiddleX &&
          cluster.isNameOnRight &&
          cluster.nameMarker
        ) {
          map.removeLayer(cluster.nameMarker);
          cluster.nameMarker = null;
        }

        if (cluster.nameMarker) {
          cluster.nameMarker.setLatLng([
            clusterCenter.location.latitude,
            clusterCenter.location.longitude,
          ]);
        } else {
          var isNameOnRight = pointX > mapMiddleX;
          cluster.isNameOnRight = isNameOnRight;
          var groupName = banana.i18n("group") + " " + alphabetizeNumber(d - 1);
          var runnerIcon = getRunnerNameMarker(
            groupName,
            cluster.color,
            isNameOnRight.value
          );
          cluster.nameMarker = L.marker(
            [clusterCenter.location.latitude, clusterCenter.location.longitude],
            { icon: runnerIcon }
          );
          cluster.nameMarker.addTo(map);
        }
        clusters[d] = cluster;
      } else {
      }
    });

    groupControl.setValues(listCompWithMarker, clusterCenters);
  }
  if (finishLineSet) {
    rankControl.setValues(finishLineCrosses);
  }
}

function getParameterByName(name) {
  try {
    name = name.replace(/[\[]/, "\\[").replace(/[\]]/, "\\]");
    var regex = new RegExp("[\\?&]" + name + "=([^&#]*)"),
      results = regex.exec(location.search);
    return results === null
      ? ""
      : decodeURIComponent(results[1].replace(/\+/g, " "));
  } catch (err) {
    return "";
  }
}

function addRasterMap(bounds, hash, maxZoom, fit, idx = 0, data = null) {
  if (fit === undefined) {
    fit = false;
  }
  var _rasterMap = L.tileLayer.wms(window.local.wmsServiceUrl + "?v=" + hash, {
    layers: window.local.eventId + (idx ? "/" + idx : ""),
    bounds: bounds,
    tileSize: 512,
    noWrap: true,
    className: "wms512",
    maxNativeZoom: maxZoom,
  });
  _rasterMap.data = data;
  _rasterMap.addTo(map);
  if (fit) {
    map.setBearing(data.rotation, { animate: false });
    map.fitBounds(bounds, { animate: false });
    map.zoomIn(0.5, { animate: false });
  }
  return _rasterMap;
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

function removeRasterMap() {
  if (rasterMap) {
    map.removeLayer(rasterMap);
    rasterMap = null;
  }
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

var connectGpsAttempts;
var connectGpsTimeoutMs;

function resetGpsConnectTimeout() {
  connectGpsAttempts = 0;
  connectGpsTimeoutMs = 100;
}
resetGpsConnectTimeout();

function bumpGpsConnectTimeout() {
  connectGpsAttempts++;

  if (connectGpsTimeoutMs === 100 && connectGpsAttempts === 20) {
    connectGpsAttempts = 0;
    connectGpsTimeoutMs = 300;
  } else if (connectGpsTimeoutMs === 300 && connectGpsAttempts === 20) {
    connectGpsAttempts = 0;
    connectGpsTimeoutMs = 1000;
  } else if (connectGpsTimeoutMs === 1000 && connectGpsAttempts === 20) {
    connectGpsAttempts = 0;
    connectGpsTimeoutMs = 3000;
  }
  if (connectGpsAttempts === 0) {
    console.debug(
      "Live GPS data stream connection error, retrying every " +
        connectGpsTimeoutMs +
        "ms"
    );
  }
}

function connectToGpsEvents() {
  gpsEventSource = new EventSource(window.local.gpsStreamUrl, {
    withCredentials: true,
  });
  // Listen for messages
  gpsEventSource.addEventListener("open", function () {});
  gpsEventSource.addEventListener("message", function (event) {
    resetGpsConnectTimeout();
    const message = JSON.parse(event.data);
    if (message.type === "ping") {
      // pass
    } else if (message.type === "locations") {
      var route = PositionArchive.fromEncoded(message.data);
      if (competitorRoutes[message.competitor]) {
        for (var i = 0; i < route.getPositionsCount(); i++) {
          competitorRoutes[message.competitor].add(route.getByIndex(i));
        }
      } else {
        competitorRoutes[message.competitor] = route;
      }
    }
  });
  gpsEventSource.addEventListener("error", function () {
    gpsEventSource.close();
    gpsEventSource = null;
    bumpGpsConnectTimeout();
    setTimeout(connectToGpsEvents, connectGpsTimeoutMs);
  });
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
  return fetch(`${langFile}?v=2023041300`)
    .then((response) => response.json())
    .then((messages) => {
      banana.load(messages, banana.locale);
    });
}
