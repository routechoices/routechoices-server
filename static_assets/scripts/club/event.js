var noDelay = noDelay === "true";

if (!navigator.canShare) {
  document.getElementById("share_buttons").remove();
}

var supportedLanguages = {
  en: "English",
  es: "Español",
  fr: "Français",
  nl: "Nederlands",
  fi: "Suomi",
};

function getLangIfSupported(code) {
  return Object.keys(supportedLanguages).includes(code) ? code : null;
}

var queryString = window.location.search;
var urlParams = new URLSearchParams(queryString);

var urlLanguage = getLangIfSupported(urlParams.get("lang"));
var storedLanguage = getLangIfSupported(window.localStorage.getItem("lang"));
var browserLanguage = getLangIfSupported(navigator.language.slice(0, 2));

var locale = urlLanguage || storedLanguage || browserLanguage || "en";

(function () {
  clock = ServerClock({ url: serverClockUrl });
  banana = new Banana();
  updateText().then(function () {
    u("#heads-up-text").text(banana.i18n("heads-up-text"));
    u("#chat-btn-text").text(banana.i18n("chat"));
    u("#loading-text").text(banana.i18n("loading-text"));
    u("#event-not-started-text").text(banana.i18n("event-not-started-text"));
    u("#club-events-link-text").text(
      banana.i18n("club-events-link-text", clubName)
    );

    u(".page-alerts").hide();
    u(".page-alert .close").on("click", function (e) {
      e.preventDefault();
      u(this).closest(".page-alert").hide();
    });

    var thumb = document.querySelector("#full_progress_bar");
    thumb.onmousedown = function (event) {
      event.preventDefault();
      document.addEventListener("mousemove", pressProgressBar);
      function onMouseUp() {
        document.removeEventListener("mouseup", onMouseUp);
        document.removeEventListener("mousemove", pressProgressBar);
      }
      document.addEventListener("mouseup", onMouseUp);
    };
    thumb.ondragstart = function () {
      return false;
    };

    u(".date-utc").each(function (el) {
      var _el = u(el);
      _el.text(dayjs(_el.data("date")).local().locale(locale).format("LLLL"));
    });
    var startDateTxt = u("#event-start-date-text").find(".date-utc").text();
    u("#event-start-date-text").text(
      banana.i18n("event-start-date-text", startDateTxt)
    );

    map = L.map("map", {
      // preferCanvas: true,
      center: [15, 0],
      maxZoom: 18,
      minZoom: 1,
      zoom: 3,
      zoomControl: false,
      scrollWheelZoom: true,
      zoomSnap: 0,
      worldCopyJump: true,
      rotate: true,
      touchRotate: true,
      rotateControl: false,
      contextmenu: true,
      contextmenuWidth: 140,
      contextmenuItems: [
        {
          text: banana.i18n("center-map"),
          callback: centerMap,
        },
        "-",
        {
          text: banana.i18n("zoom-in"),
          callback: zoomIn,
        },
        {
          text: banana.i18n("zoom-out"),
          callback: zoomOut,
        },
      ],
    });
    panControl = L.control.pan();
    zoomControl = L.control.zoom();
    rotateControl = L.control.rotate({ closeOnZeroBearing: false });
    scaleControl = L.control.scale({
      imperial: false,
      updateWhenIdle: true,
      position: "bottomleft",
    });
    if (showControls) {
      panControl.addTo(map);
      zoomControl.addTo(map);
      rotateControl.addTo(map);
    }
    scaleControl.addTo(map);

    map.doubleClickZoom.disable();
    map.on("dblclick", onPressCustomMassStart);
    map.on("move", function () {
      drawCompetitors();
    });

    reqwest({
      url: eventUrl,
      withCredentials: true,
      crossOrigin: true,
      type: "json",
      success: function (response) {
        backdropMaps[response.event.backdrop].addTo(map);
        var now = new Date();
        var startEvent = new Date(response.event.start_date);
        endEvent = new Date(response.event.end_date);
        if (startEvent > now) {
          u(".event-tool").hide();

          map.fitWorld({ animate: false }).zoomIn(null, { animate: false });
          u("#eventLoadingModal").remove();
          var preRaceModal = new bootstrap.Modal(
            document.getElementById("eventNotStartedModal"),
            { backdrop: "static", keyboard: false }
          );
          document
            .getElementById("eventNotStartedModal")
            .addEventListener("hide.bs.modal", function (e) {
              e.preventDefault();
            });
          preRaceModal.show();
          window.setInterval(function () {
            if (new Date() > startEvent) {
              location.reload();
            }
          }, 1e3);
        } else {
          u("#runners_show_button").on("click", toggleCompetitorList);
          u("#live_button")
            .on("click", selectLiveMode)
            .text(banana.i18n("live-mode"));
          u("#replay_button")
            .on("click", selectReplayMode)
            .text(banana.i18n("replay-mode"));
          u("#play_pause_button").on("click", pressPlayPauseButton);
          u("#next_button").on("click", function (e) {
            e.preventDefault();
            playbackRate = playbackRate * 2;
          });
          u("#prev_button").on("click", function (e) {
            e.preventDefault();
            playbackRate = Math.max(1, playbackRate / 2);
          });
          u("#real_time_button")
            .on("click", function (e) {
              e.preventDefault();
              isRealTime = true;
              if (resetMassStartContextMenuItem) {
                map.contextmenu.removeItem(resetMassStartContextMenuItem);
                resetMassStartContextMenuItem = null;
              }
              u("#real_time_button").addClass("active");
              u("#mass_start_button").removeClass("active");
            })
            .text(banana.i18n("real-time"));
          u("#mass_start_button")
            .on("click", function (e) {
              e.preventDefault();
              onPressResetMassStart();
            })
            .text(banana.i18n("mass-start"));
          u("#chat_show_button").on("click", displayChat);
          u("#options_show_button").on("click", displayOptions);
          u("#full_progress_bar").on("click", pressProgressBar);
          u("#share_button").on("click", shareUrl);
          if (response.event.chat_enabled) {
            u("#chat_button_group").removeClass("d-none");
            connectToChatEvents();
          }
          if (endEvent > now) {
            isLiveEvent = true;
          } else {
            clock.stopRefreshes();
          }
          qrUrl = response.event.shortcut;
          liveUrl = response.data;
          sendInterval = response.event.send_interval;
          tailLength = response.event.tail_length;
          if (response.maps.length) {
            var MapLayers = {};
            for (var i = 0; i < response.maps.length; i++) {
              var m = response.maps[i];
              if (m.default) {
                m.title = m.title
                  ? u("<span/>").text(m.title).html()
                  : '<i class="fa fa-star"></i> Main Map';
                var bounds = [
                  [m.coordinates.topLeft.lat, m.coordinates.topLeft.lon],
                  [m.coordinates.topRight.lat, m.coordinates.topRight.lon],
                  [
                    m.coordinates.bottomRight.lat,
                    m.coordinates.bottomRight.lon,
                  ],
                  [m.coordinates.bottomLeft.lat, m.coordinates.bottomLeft.lon],
                ];
                addRasterMap(bounds, m.hash, true);
                MapLayers[m.title] = rasterMap;
              } else {
                var bounds = [
                  [m.coordinates.topLeft.lat, m.coordinates.topLeft.lon],
                  [m.coordinates.topRight.lat, m.coordinates.topRight.lon],
                  [
                    m.coordinates.bottomRight.lat,
                    m.coordinates.bottomRight.lon,
                  ],
                  [m.coordinates.bottomLeft.lat, m.coordinates.bottomLeft.lon],
                ];
                MapLayers[m.title] = L.tileLayer.wms(
                  wmsServiceUrl + "?hash=" + m.hash,
                  {
                    layers: eventId + "/" + i,
                    bounds: bounds,
                    tileSize: 512,
                    noWrap: true,
                  }
                );
              }
            }
            if (response.maps.length > 1) {
              L.control
                .layers(MapLayers, null, { collapsed: false })
                .addTo(map);
              map.on("baselayerchange", function (e) {
                console.log(e);
                map.fitBounds(e.layer.options.bounds);
              });
            }
          } else {
            zoomOnRunners = true;
          }
          if (response.announcement) {
            prevNotice = response.announcement;
            u("#alert-text").text(prevNotice);
            u(".page-alerts").show();
          }
          if (!setFinishLineContextMenuItem) {
            setFinishLineContextMenuItem = map.contextmenu.insertItem(
              {
                text: banana.i18n("draw-finish-line"),
                callback: drawFinishLine,
              },
              1
            );
          }
          onStart();
        }
      },
      error: function () {
        u("#eventLoadingModal").remove();
        swal({ text: "Something went wrong", title: "error", type: "error" });
      },
    });
  });
})();
