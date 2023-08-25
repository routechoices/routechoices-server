(function () {
  window.addEventListener("resize", onAppResize);
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
              (el.matches("#competitorList") || el.matches("#optionsSidebar"))
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
    locateControl = L.control
      .locate({
        flyTo: true,
        returnToPrevBounds: true,
        showCompass: false,
        showPopup: false,
        locateOptions: {
          watch: true,
          enableHighAccuracy: true,
        },
      })
      .addTo(map);
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
        if (response.event.backdrop === "blank") {
          u("#map").css({ background: "#fff" });
        } else {
          var layer = backdropMaps[response.event.backdrop];
          layer.addTo(map);
          layer.nickname = response.event.backdrop;
          backgroundLayer = layer;
        }
        var now = clock.now();
        startEvent = new Date(response.event.start_date);
        endEvent = new Date(response.event.end_date);
        if (startEvent > now) {
          try {
            map.remove();
          } catch {}
          u(".event-tool").hide();
          u("#eventLoadingModal").remove();
          u("#permanent-sidebar").remove();
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
          u("#map").removeClass("no-sidebar");
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
            .text(banana.i18n("switch-replay-mode"));
          u("#play_pause_button").on("click", pressPlayPauseButton);
          u("#next_button").on("click", function (e) {
            e.preventDefault();
            playbackRate = playbackRate * 2;
          });
          u("#prev_button").on("click", function (e) {
            e.preventDefault();
            playbackRate = Math.max(1, playbackRate / 2);
          });
          u("#real_time_button").on("click", function (e) {
            e.preventDefault();
            isRealTime = true;
            if (resetMassStartContextMenuItem) {
              map.contextmenu.removeItem(resetMassStartContextMenuItem);
              resetMassStartContextMenuItem = null;
            }
            u("#real_time_button").addClass("active");
            u("#mass_start_button").removeClass("active");
          });
          u("#real_time_text").text(banana.i18n("real-time"));
          u("#mass_start_button").on("click", function (e) {
            e.preventDefault();
            onPressResetMassStart();
          });
          u("#mass_start_text").text(banana.i18n("mass-start"));
          u("#options_show_button").on("click", displayOptions);
          u("#full_progress_bar").on("click", pressProgressBar);
          u("#share_button").on("click", shareUrl);
          if (endEvent > now) {
            isLiveEvent = true;
            eventStateControl.setLive();
            u("#archived_event_button").hide();
          } else {
            eventStateControl.setReplay();
            u("#archived_event_button").text(banana.i18n("archived-event"));
          }
          qrUrl = response.event.shortcut;
          liveUrl = window.local.dataUrl;
          sendInterval = response.event.send_interval;
          tailLength = response.event.tail_length;
          prevMapsJSONData = JSON.stringify(response.maps);
          if (response.maps.length) {
            var mapChoices = {};
            for (var i = 0; i < response.maps.length; i++) {
              var mapData = response.maps[i];
              mapData.title = mapData.title
                ? u("<span/>").text(mapData.title).text()
                : '<i class="fa-solid fa-star"></i> Main Map';
              var layer = addRasterMapLayer(mapData, i);
              mapChoices[mapData.title] = layer;
              if (mapData.default) {
                setRasterMap(layer, true);
              }
            }
            if (response.maps.length > 1) {
              mapSelectorLayer = L.control.layers(mapChoices, null, {
                collapsed: false,
              });
              mapSelectorLayer.addTo(map);
              map.on("baselayerchange", onLayerChange);
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
