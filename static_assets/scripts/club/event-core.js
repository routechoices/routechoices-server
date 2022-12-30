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
var locale = null;
var map = null;
var isLiveMode = false;
var liveUrl = null;
var isLiveEvent = false;
var isRealTime = true;
var isCustomStart = false;
var competitorList = [];
var competitorRoutes = {};
var routesLastFetched = -Infinity;
var eventDataLastFetch = -Infinity;
var fetchPositionInterval = 10;
var playbackRate = 8;
var playbackPaused = true;
var prevDisplayRefresh = 0;
var tailLength = 60;
var isCurrentlyFetchingRoutes = false;
var isFetchingEventData = false;
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
      '<svg style="color: #fff;margin-top: -5px;margin-left: -10px;" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 44 44" preserveAspectRatio="xMidYMid meet" x="955"  stroke="#fff" width="20"><g fill="none" fill-rule="evenodd" stroke-width="2"><circle cx="22" cy="22" r="1"><animate attributeName="r" begin="0s" dur="1.8s" values="1; 20" calcMode="spline" keyTimes="0; 1" keySplines="0.165, 0.84, 0.44, 1" repeatCount="indefinite"/><animate attributeName="stroke-opacity" begin="0s" dur="1.8s" values="1; 0" calcMode="spline" keyTimes="0; 1" keySplines="0.3, 0.61, 0.355, 1" repeatCount="indefinite"/></circle><circle cx="22" cy="22" r="1"><animate attributeName="r" begin="-0.9s" dur="1.8s" values="1; 20" calcMode="spline" keyTimes="0; 1" keySplines="0.165, 0.84, 0.44, 1" repeatCount="indefinite"/><animate attributeName="stroke-opacity" begin="-0.9s" dur="1.8s" values="1; 0" calcMode="spline" keyTimes="0; 1" keySplines="0.3, 0.61, 0.355, 1" repeatCount="indefinite"/></circle></g></svg> ' +
      banana.i18n("live-mode");
    u(this._div).css({
      display: "block",
      fontSize: "20px",
      color: "#fff",
      backgroundColor: "red",
      borderRadius: "15px",
      padding: "3px 20px",
      fontStyle: "italic",
      fontWeight: "bold",
      textTransform: "uppercase",
    });
  },
  setReplay() {
    this._div.innerHTML = banana.i18n("replay-mode");
    u(this._div).css({
      display: "block",
      fontSize: "20px",
      color: "#fff",
      backgroundColor: "#666",
      borderRadius: "15px",
      padding: "3px 15px",
      fontStyle: "normal",
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
          "<h6>" +
          banana.i18n("ranking") +
          "</h6><label>" +
          banana.i18n("crossing-count") +
          '</label>&nbsp;<input type="number" min="1" id="crossing-time" step="1" value="1" class="cross-count" style="width: 38px">' +
          "</div>"
      );
    }
    var innerOut = u('<div class="result-name-list"/>');
    ranking.sort(function (a, b) {
      return getRelativeTime(a.time) - getRelativeTime(b.time);
    });
    ranking.forEach(function (c, i) {
      innerOut.append(
        '<div style="clear:both;white-space:nowrap;width:200px;height:1em"><span style="float:left;display:inline-block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;width:135px;">' +
          (i + 1) +
          ' <span style="color: ' +
          c.competitor.color +
          '">⬤</span> ' +
          u("<span/>").text(c.competitor.name).html() +
          '</span><span style="float:right;display:inline-block;white-space:nowrap;overflow:hidden;width:55px;font-feature-settings:tnum;font-variant-numeric:tabular-nums lining-nums;margin-right:10px" title="' +
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
          '<div style="clear:both;white-space:nowrap;width:200px;height:1em"><span style="float:left;display:inline-block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;width:195px;"><span style="color: ' +
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

function getRunnerIcon(color, faded = false) {
  var iconSize = 16;
  var liveColor = tinycolor(color).setAlpha(faded ? 0.4 : 0.75);
  var isDark = getContrastYIQ(color) === "dark";
  var svgRect = `<svg viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg"><circle fill="${liveColor.toRgbString()}" stroke="${
    isDark ? "white" : "black"
  }" stroke-width="1px" cx="8" cy="8" r="6"/></svg>`;
  var runnerIcon = L.icon({
    iconUrl: encodeURI("data:image/svg+xml," + svgRect),
    iconSize: [iconSize, iconSize],
    shadowSize: [iconSize, iconSize],
    iconAnchor: [iconSize / 2, iconSize / 2],
    shadowAnchor: [0, 0],
    popupAnchor: [0, 0],
  });
  return runnerIcon;
}

function getRunnerNameMarker(name, color, rightSide, faded = false) {
  var iconHtml =
    '<span style="opacity: ' +
    (faded ? 0.4 : 0.75) +
    ";color: " +
    color +
    '">' +
    u("<span/>").text(name).html() +
    "</span>";
  var iconClass = "runner-icon runner-icon-" + getContrastYIQ(color);
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
  if (isLiveEvent) {
    selectLiveMode();
  } else {
    u("#live_button").remove();
    u("#replay_button").remove();
    selectReplayMode();
  }
  u(".main").removeClass("loading");
  u(".sidebar").removeClass("loading");
  u(".time_bar").removeClass("loading");
  map.invalidateSize();
  fetchCompetitorRoutes(null, true);
  appHeight();
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
  u(".time_bar").removeClass("replay_mode");
  u(".main").removeClass("replay_mode");
  u(".sidebar").removeClass("replay_mode");

  eventStateControl.setLive();
  if (setMassStartContextMenuItem) {
    map.contextmenu.removeItem(setMassStartContextMenuItem);
    setMassStartContextMenuItem = null;
  }
  if (resetMassStartContextMenuItem) {
    map.contextmenu.removeItem(resetMassStartContextMenuItem);
    resetMassStartContextMenuItem = null;
  }
  u("#live_button").addClass("active");
  u("#replay_button").removeClass("active");
  u("#real_time_button").removeClass("active");
  u("#mass_start_button").removeClass("active");
  u("#replay_mode_buttons").hide();
  u("#replay_control_buttons").hide();

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
    if (ts - eventDataLastFetch > 30 * 1e3 && !isFetchingEventData) {
      refreshEventData();
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
    var isStillLive = +endEvent >= +clock.now();
    if (!isStillLive) {
      u("#live_button").remove();
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

  u("#full_progress_bar").removeClass("d-none");
  u("#real_time_button").addClass("active");
  u("#mass_start_button").removeClass("active");
  u(".time_bar").addClass("replay_mode");
  u(".main").addClass("replay_mode");
  u(".sidebar").addClass("replay_mode");

  eventStateControl.setReplay();
  u("#live_button").removeClass("active");
  u("#replay_button").addClass("active");
  u("#replay_mode_buttons").css({ display: "inline-block" });
  u("#replay_control_buttons").css({ display: "inline-block" });
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
  prevShownTime = getCompetitionStartDate();
  playbackPaused = true;
  prevDisplayRefresh = performance.now();
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
    if (
      isLiveEvent &&
      performance.now() - eventDataLastFetch > 30 * 1e3 &&
      !isFetchingEventData
    ) {
      refreshEventData();
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
    }
    prevShownTime = currentTime;
    if (!isLiveMode) {
      window.requestAnimationFrame(whileReplay);
    }
  }
  whileReplay(performance.now());
}

function fetchCompetitorRoutes(url) {
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
      var runnerPoints = [];
      response.competitors.forEach(function (competitor, idx) {
        if (competitor.encoded_data) {
          var route = PositionArchive.fromEncoded(competitor.encoded_data);
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
      u("#eventLoadingModal").remove();
    },
    error: function () {
      isCurrentlyFetchingRoutes = false;
    },
  });
}

function refreshEventData() {
  isFetchingEventData = true;
  reqwest({
    url: window.local.eventUrl,
    withCredentials: true,
    crossOrigin: true,
    type: "json",
    success: function (response) {
      eventDataLastFetch = performance.now();
      isFetchingEventData = false;
      if (response.announcement && response.announcement != prevNotice) {
        prevNotice = response.announcement;
        u("#alert-text").text(prevNotice);
        u(".page-alert").show();
      }
      if (JSON.stringify(response.maps) !== prevMapsJSONData) {
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
        if (currentMapNewData || response.maps.length === 0) {
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
                  ? '<i class="fa fa-star"></i> Main Map'
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
                !currentMapNewData,
                i,
                m
              );
              mapChoices[m.title] = rasterMap;
            } else {
              m.title =
                !m.title && m.default
                  ? '<i class="fa fa-star"></i> Main Map'
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
            mapSelectorLayer.addTo(map);
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
  map.invalidateSize();
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
  map.invalidateSize();
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
  if (c.displayFullRoute) {
    c.displayFullRoute = null;
    u("#fullRouteIcon-" + c.id).attr({ fill: null });
  } else {
    c.displayFullRoute = true;
    u("#fullRouteIcon-" + c.id).attr({ fill: "#18bc9c" });
  }
}

function zoomOnCompetitor(compr) {
  if (compr.focusing) {
    return;
  }
  compr.focusing = true;
  var route = competitorRoutes[compr.id];
  if (!route) return;
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
    comp.focused = false;
    u("#focusedIcon-" + comp.id).removeClass("route-focused");
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

function displayCompetitorList(force) {
  if (!force && optionDisplayed) {
    return;
  }
  optionDisplayed = false;
  var listDiv = u(
    '<div id="listCompetitor" style="overflow-y: auto;margin-top:3px;"/>'
  );
  nbShown = 0;
  competitorList.forEach(function (competitor, ii) {
    competitor.color = competitor.color || getColor(ii);

    competitor.isShown =
      typeof competitor.isShown === "undefined"
        ? nbShown < maxParticipantsDisplayed
        : competitor.isShown;
    nbShown += competitor.isShown ? 1 : 0;
    var div = u('<div class="card-body" style="padding:5px 10px 2px 10px;"/>');
    div.html(
      '<div class="float-start color-tag" style="margin-right: 5px; cursor: pointer"><i class="media-object fa fa-circle fa-3x icon-sidebar" style="color:' +
        competitor.color +
        '"></i></div>\
        <div><div style="white-space: nowrap; text-overflow: ellipsis; overflow: hidden;padding-left: 3px"><b>' +
        u("<div/>").text(competitor.name).html() +
        '</b></div>\
        <div style="white-space: nowrap; text-overflow: ellipsis; overflow: hidden;padding-left: 3px" class="' +
        (competitor.isShown ? "route-displayed" : "route-not-displayed") +
        '">' +
        // toggle on off
        '<button type="button" class="toggle_competitor_btn btn btn-default btn-sm" aria-label="toggle ' +
        (competitor.isShown ? "off" : "on") +
        '" style="padding: 0 3px 0 0" data-bs-toggle="tooltip" data-bs-title="' +
        banana.i18n("toggle") +
        '"><i class="fa fa-toggle-' +
        (competitor.isShown ? "on" : "off") +
        '" ></i></button>' +
        // toggle follow competitor
        '<button type="button" class="focus_competitor_btn btn btn-default btn-sm" aria-label="focus on competitor" data-bs-toggle="tooltip" data-bs-title="' +
        banana.i18n("follow") +
        '" style="padding: 0 3px 0 0;margin-left:1px">' +
        '<i class="fa-solid fa-crosshairs' +
        (competitor.focused ? " route-focused" : "") +
        '" id="focusedIcon-' +
        competitor.id +
        '"></i></button>' +
        // center on competitor
        '<button type="button" class="center_competitor_btn btn btn-default btn-sm" aria-label="focus" style="padding: 0" data-bs-toggle="tooltip" data-bs-title="' +
        banana.i18n("center") +
        '"><i class="fa fa-map-marker"></i></button>' +
        // toggle full route
        '<button type="button" class="full_competitor_btn btn btn-default btn-sm" aria-label="full route" style="padding: 0" data-bs-toggle="tooltip" data-bs-title="' +
        banana.i18n("full-route") +
        '"><svg id="fullRouteIcon-' +
        competitor.id +
        '" ' +
        (competitor.displayFullRoute ? 'fill="#18bc9c"' : "") +
        ' viewBox="0 0 48 48" width="20px"><path d="M28.65 42.95q-2.85 0-4.775-2.075Q21.95 38.8 21.95 35.45q0-2.5 1.325-4.4 1.325-1.9 3.125-3.1 1.8-1.2 3.7-1.825 1.9-.625 3.2-.675-.15-2.4-1.1-3.475-.95-1.075-2.75-1.075-2 0-3.7 1.15-1.7 1.15-4.5 5.1-2.85 4.05-5.075 5.65-2.225 1.6-4.675 1.6-2.5 0-4.475-1.625Q5.05 31.15 5.05 27.15q0-1.45 1.025-3.7T9.65 17.2q1.9-2.55 2.5-3.725.6-1.175.6-2.175 0-.55-.325-.875-.325-.325-.925-.325-.3 0-.8.15t-1 .6q-1 .55-1.825.525-.825-.025-1.375-.625-.7-.55-.7-1.525 0-.975.7-1.625 1.15-1 2.475-1.55Q10.3 5.5 11.75 5.5q2.35 0 3.9 1.65Q17.2 8.8 17.2 11q0 2.25-.95 4.15-.95 1.9-3.2 5.15-2.25 3.4-2.875 4.625T9.55 27.45q0 1.35.775 1.775.775.425 1.625.425 1.2 0 2.4-1.125t3.55-4.275q3.35-4.4 6-6.175 2.65-1.775 5.95-1.775 3.15 0 5.425 2.275T37.85 25.3h2.9q1 0 1.625.625T43 27.5q0 1-.625 1.65-.625.65-1.625.65h-2.9q-.55 8.8-3.9 10.975-3.35 2.175-5.3 2.175Zm.15-4.65q1.05 0 2.6-1.525t1.95-6.725q-1.9.2-4.375 1.55T26.5 35.95q0 1.1.575 1.725t1.725.625Z"/>' +
        "</svg></button>" +
        '<span class="float-end"><small class="speedometer"></small> <small class="odometer"></small></span>\
        </div>\
        </div>'
    );
    var diva = u(
      '<div class="card" style="background-color:transparent; margin-top: 3px";/>'
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
      .find(".toggle_competitor_btn")
      .on("click", function (e) {
        e.preventDefault();
        var icon = u(this).find("i");
        if (icon.hasClass("fa-toggle-on")) {
          icon.removeClass("fa-toggle-on").addClass("fa-toggle-off");
          icon
            .parent()
            .parent()
            .removeClass("route-displayed")
            .addClass("route-not-displayed");
          competitor.isShown = false;

          competitor.focused = false;
          u("#focusedIcon-" + competitor.id).removeClass("route-focused");

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
          icon.removeClass("fa-toggle-off").addClass("fa-toggle-on");
          icon
            .parent()
            .parent()
            .removeClass("route-not-displayed")
            .addClass("route-displayed");
          competitor.isShown = true;
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
    var div = u("<div/>");
    var txt = banana.i18n("no-competitors");
    div.html("<h3>" + txt + "</h3>");
    listDiv.append(div);
  }
  if (searchText === null) {
    var mainDiv = u(
      '<div id="competitorSidebar" style="display: flex;flex-direction: column;"/>'
    );
    var topDiv = u("<div/>");
    topDiv.append(
      u('<div style="text-align:right;margin-bottom:-15px"/>').append(
        u('<button class="btn btn-default btn-sm" aria-label="close"/>')
          .html('<i class="fa fa-times"></i>')
          .on("click", toggleCompetitorList)
      )
    );
    if (competitorList.length) {
      var hideAllTxt = banana.i18n("hide-all");
      var showAllTxt = banana.i18n("show-all");
      topDiv.append(
        '<div style="text-align: center;white-space: nowrap">' +
          '<button id="showAllCompetitorBtn" class="btn btn-default"><i class="fa fa-eye"></i> ' +
          showAllTxt +
          "</button>" +
          '<button id="hideAllCompetitorBtn" class="btn btn-default"><i class="fa fa-eye-slash"></i> ' +
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
          u("#focusedIcon-" + competitor.id).removeClass("route-focused");

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
      listDiv.addClass("with_search_bar");
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
    u('<div style="text-align:right;"/>').append(
      u('<button class="btn btn-default btn-sm" aria-label="close"/>')
        .html('<i class="fa fa-times"></i>')
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
      "<h4>" +
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
        "<h4>" +
        banana.i18n("map-controls") +
        "</h4>" +
        '<button type="button" class="toggle_controls_btn btn btn-default btn-sm"><i class="fa fa-toggle-' +
        (showControls ? "on" : "off") +
        '"></i> ' +
        banana.i18n("show-map-controls") +
        "</button>" +
        "<h4>" +
        banana.i18n("groupings") +
        "</h4>" +
        '<button type="button" class="toggle_cluster_btn btn btn-default btn-sm"><i class="fa fa-toggle-' +
        (showClusters ? "on" : "off") +
        '"></i> ' +
        banana.i18n("show-groupings") +
        "</button>" +
        '<h4><i class="fa fa-language"></i> ' +
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
<p style="text-align:center">
<img style="padding:10px" src="${qrDataUrl}" alt="qr"><br/>
<a class="small" style="font-weight: bold" href="${qrUrl}">${qrUrl.replace(
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
    .find(".toggle_cluster_btn")
    .on("click", function (e) {
      if (showClusters) {
        u(".toggle_cluster_btn")
          .find(".fa-toggle-on")
          .removeClass("fa-toggle-on")
          .addClass("fa-toggle-off");
        showClusters = false;
        map.removeControl(groupControl);
        Object.values(clusters).forEach(function (c) {
          map.removeLayer(c.mapMarker);
          map.removeLayer(c.nameMarker);
        });
        clusters = {};
      } else {
        u(".toggle_cluster_btn")
          .find(".fa-toggle-off")
          .removeClass("fa-toggle-off")
          .addClass("fa-toggle-on");
        groupControl = L.control.grouping({ position: "topright" });
        map.addControl(groupControl);
        showClusters = true;
      }
    });
  u(mainDiv)
    .find(".toggle_controls_btn")
    .on("click", function (e) {
      if (showControls) {
        u(".toggle_controls_btn")
          .find(".fa-toggle-on")
          .removeClass("fa-toggle-on")
          .addClass("fa-toggle-off");
        showControls = false;
        map.removeControl(panControl);
        map.removeControl(zoomControl);
        map.removeControl(rotateControl);
      } else {
        u(".toggle_controls_btn")
          .find(".fa-toggle-off")
          .removeClass("fa-toggle-off")
          .addClass("fa-toggle-on");
        map.addControl(panControl);
        map.addControl(zoomControl);
        map.addControl(rotateControl);
        showControls = true;
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

function getProgressBarText(currentTime) {
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
    result += t > 3600 ? Math.floor(t / 3600) + ":" : "";
    result += to2digits((t / 60) % 60) + ":" + to2digits(t % 60);
  } else {
    var t = Math.round(viewedTime / 1e3);
    if (t === 0) {
      return "00:00:00";
    }
    if (
      dayjs(getCompetitionStartDate()).format("YYYY-MM-DD") !==
      dayjs(getCompetitionEndDate()).format("YYYY-MM-DD")
    ) {
      result = dayjs(viewedTime).format("YYYY-MM-DD HH:mm:ss");
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
    var html = '<i class="fa fa-play"></i> x' + playbackRate;
    if (u("#play_pause_button").html() != html) {
      u("#play_pause_button").html(html);
    }
  } else {
    var html = '<i class="fa fa-pause"></i> x' + playbackRate;
    if (u("#play_pause_button").html() != html) {
      u("#play_pause_button").html(html);
    }
  }
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
  u("#progress_bar_text").html(getProgressBarText(currentTime));

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
              true
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
          var runnerIcon = getRunnerIcon(competitor.color);
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
            isNameOnRight
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
            isNameOnRight
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
    map.fitBounds(bounds);
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
  return fetch(`${langFile}?v=2022121300`)
    .then((response) => response.json())
    .then((messages) => {
      banana.load(messages, banana.locale);
    });
}
