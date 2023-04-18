(function () {
  window.addEventListener("resize", appHeight);
  if (!navigator.canShare) {
    document.getElementById("share_buttons").remove();
  }
  var queryString = window.location.search;
  var urlParams = new URLSearchParams(queryString);

  var urlLanguage = getLangIfSupported(urlParams.get("lang"));
  var storedLanguage = getLangIfSupported(window.localStorage.getItem("lang"));
  var browserLanguage = getLangIfSupported(navigator.language.slice(0, 2));
  locale = urlLanguage || storedLanguage || browserLanguage || "en";
  clock = ServerClock({ url: window.local.serverClockUrl, burstSize: 1 });
  setTimeout(clock.stopRefreshes, 1000);
  backdropMaps["blank"] = L.tileLayer(
    'data:image/svg+xml,<svg viewBox="0 0 512 512" xmlns="http://www.w3.org/2000/svg"><rect fill="rgb(256,256,256)" width="512" height="512"/></svg>',
    {
      attribution: "",
      tileSize: 512,
      className: "wms512",
    }
  );
  banana = new Banana();
  updateText().then(function () {
    u("#heads-up-text").text(banana.i18n("heads-up-text"));
    u("#export-text").text(banana.i18n("export"));
    u("#loading-text").text(banana.i18n("loading-text"));
    u(".cancel-text").text(banana.i18n("cancel"));
    u(".save-text").text(banana.i18n("save"));
    u("#event-not-started-text").text(banana.i18n("event-not-started-text"));
    u("#club-events-link-text").text(
      banana.i18n("club-events-link-text", window.local.clubName)
    );
    toast = new bootstrap.Toast(document.getElementById("text-alert"), {
      animation: false,
      autohide: false,
    });
    toast.hide();

    document
      .querySelector(".navbar")
      .addEventListener("touchmove", function (e) {
        e.preventDefault();
        e.stopPropagation();
      });
    document
      .querySelector("#bottom-div")
      .addEventListener("touchmove", function (e) {
        e.preventDefault();
      });
    document
      .querySelector("#sidebar")
      .addEventListener("touchmove", function (e) {
        var path = e.composedPath();
        if (
          !path.find(function (el) {
            return (
              el.matches &&
              (el.matches("#listCompetitor") || el.matches("#listOptions"))
            );
          })
        ) {
          e.preventDefault();
        }
      });
    document
      .querySelector("#myFooter")
      .addEventListener("touchmove", function (e) {
        e.preventDefault();
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
    thumb.ondragstart = function (e) {
      e.preventDefault();
      return false;
    };
    thumb.addEventListener("touchmove", touchProgressBar);

    var startDateTxt = dayjs(
      u("#event-start-date-text").find(".date-utc").data("date")
    )
      .local()
      .locale(locale)
      .format("LLLL");
    u("#event-start-date-text").text(
      banana.i18n("event-start-date-text", startDateTxt)
    );

    map = L.map("map", {
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

    map.on("movestart", function () {
      isMapMoving = true;
    });
    map.on("moveend", function () {
      isMapMoving = false;
    });
    map.on("zoomstart", function () {
      isMapMoving = true;
    });
    map.on("zoomend", function () {
      isMapMoving = false;
    });

    eventStateControl = L.control.eventState();
    coordsControl = L.control.mapCenterCoord({
      position: "bottomright",
      icon: false,
      template: "{y}, {x}",
    });
    panControl = L.control.pan();
    zoomControl = L.control.zoom();
    rotateControl = L.control.rotate({ closeOnZeroBearing: false });
    scaleControl = L.control.scale({
      imperial: false,
      updateWhenIdle: true,
      position: "bottomleft",
    });
    eventStateControl.addTo(map);
    eventStateControl.hide();
    if (showControls) {
      panControl.addTo(map);
      zoomControl.addTo(map);
      rotateControl.addTo(map);
    }
    coordsControl.addTo(map);
    scaleControl.addTo(map);
    map.doubleClickZoom.disable();
    map.on("dblclick", onPressCustomMassStart);
    reqwest({
      url: window.local.eventUrl,
      withCredentials: true,
      crossOrigin: true,
      type: "json",
      success: function (response) {
        backdropMaps[response.event.backdrop || "blank"].addTo(map);
        var now = clock.now();
        startEvent = new Date(response.event.start_date);
        endEvent = new Date(response.event.end_date);
        if (startEvent > now) {
          try {
            map.remove();
          } catch {}
          u(".event-tool").hide();
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
          hideSidebar();
          u("#export-nav-item").remove();
          preRaceModal.show();
          window.setInterval(function () {
            if (clock.now() > startEvent) {
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
          u("#options_show_button").on("click", displayOptions);
          u("#full_progress_bar").on("click", pressProgressBar);
          u("#share_button").on("click", shareUrl);
          if (endEvent > now) {
            isLiveEvent = true;
            eventStateControl.setLive();
          } else {
            eventStateControl.setReplay();
          }
          qrUrl = response.event.shortcut;
          liveUrl = window.local.dataUrl;
          sendInterval = response.event.send_interval;
          tailLength = response.event.tail_length;
          prevMapsJSONData = JSON.stringify(response.maps);
          if (response.maps.length) {
            var mapChoices = {};
            for (var i = 0; i < response.maps.length; i++) {
              var m = response.maps[i];
              if (m.default) {
                m.title = m.title
                  ? u("<span/>").text(m.title).html()
                  : '<i class="fa-solid fa-star"></i> Main Map';
                var bounds = [
                  [m.coordinates.topLeft.lat, m.coordinates.topLeft.lon],
                  [m.coordinates.topRight.lat, m.coordinates.topRight.lon],
                  [
                    m.coordinates.bottomRight.lat,
                    m.coordinates.bottomRight.lon,
                  ],
                  [m.coordinates.bottomLeft.lat, m.coordinates.bottomLeft.lon],
                ];
                rasterMap = addRasterMap(
                  bounds,
                  m.hash,
                  m.max_zoom,
                  true,
                  0,
                  m
                );
                mapChoices[m.title] = rasterMap;
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
              map.on("baselayerchange", function (e) {
                map.setBearing(e.layer.data.rotation, { animate: false });
                map.fitBounds(e.layer.options.bounds, { animate: false });
                map.zoomIn(0.5, { animate: false });
                rasterMap = e.layer;
              });
            }
          } else {
            zoomOnRunners = true;
          }
          if (response.announcement) {
            prevNotice = response.announcement;
            u(".text-alert-content").text(prevNotice);
            toast.show();
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
        setInterval(refreshEventData, 25 * 1e3);
      },
      error: function () {
        u("#eventLoadingModal").remove();
        swal({ text: "Something went wrong", title: "error", type: "error" });
      },
    });
  });
})();
