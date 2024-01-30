function RCEvent(infoURL, clockURL) {
  var infoURL = infoURL;
  var bgLayer = null;
  var clock = ServerClock({ url: clockURL, burstSize: 1 });
  setTimeout(clock.stopRefreshes, 1000);
  var eventStart = null;
  var eventEnd = null;
  var map = null;
  var showControls = false;
  var locateControl;
  var eventStateControl;
  var coordsControl;
  var panControl;
  var zoomControl;
  var rotateControl;
  var scaleControl;
  var isLive = false;
  var isLiveEvent = false;
  var shortcutURL = "";
  var dataURL;
  var sendInterval = 5;
  var tailLength = 60;
  var previousFetchMapData = null;
  var previousFetchAnouncement = null;
  var zoomOnRunners = false;
  var rasterMapLayer;
  var mapOpacity = 1;
  var toastAnouncement = new bootstrap.Toast(
    document.getElementById("text-alert"),
    {
      animation: true,
      autohide: false,
    }
  );
  toastAnouncement.hide();

  var isRealTime = true;
  var isCustomStart = false;
  var competitorList = {};
  var competitorRoutes = {};
  var competitorBatteyLevels = {};
  var routesLastFetched = -Infinity;
  var fetchPositionInterval = 10;
  var playbackRate = 8;
  var playbackPaused = true;
  var prevDisplayRefresh = 0;
  var prevMeterDisplayRefresh = 0;
  var isCurrentlyFetchingRoutes = false;
  var currentTime = 0;
  var optionDisplayed = false;
  var searchText = null;
  var resetMassStartContextMenuItem = null;
  var setMassStartContextMenuItem = null;
  var removeFinishLineContextMenuItem = null;
  var clusters = {};
  var finishLineCrosses = [];
  var finishLinePoints = [];
  var finishLinePoly = null;
  var finishLineSet = false;
  var showClusters = false;
  var showControls = false;
  var colorModal = new bootstrap.Modal(document.getElementById("colorModal"));
  var mapSelectorLayer = null;
  var sidebarShown = true;
  var isMapMoving = false;
  var oldCrossingForNTimes = 1;
  var intersectionCheckZoom = 18;
  var showUserLocation = false;
  var showAll = true;
  var rankControl = null;
  var competitorsMinCustomOffset = null;
  class CompetitorSidebarEl extends HTMLElement {
    constructor() {
      super();

      const competitorId = this.getAttribute("competitor-id");
      const i = this.getAttribute("index");

      const competitor = competitorList[competitorId];
      if (!competitor) {
        this.innerHTML = "";
        return;
      }

      if (typeof competitor.isShown === "undefined") {
        competitor.isShown = true;
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
              "aria-label": "toggle competitor",
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
                commonDiv
                  .find(".full-route-icon")
                  .attr({ fill: "var(--bs-body-color)" });
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
                commonDiv
                  .find(".battery-indicator")
                  .addClass("d-none")
                  .removeClass("if-live");
                updateCompetitor(competitor);
              } else {
                competitor.isShown = true;
                commonDiv
                  .removeClass("route-not-displayed")
                  .addClass("route-displayed");
                commonDiv.find("button").attr({ disabled: false });
                if (isLive) {
                  commonDiv
                    .find(".battery-indicator")
                    .removeClass("d-none")
                    .addClass("if-live");
                }

                var colorTag = commonDiv.parent().find(".color-tag");
                colorTag.find("i.fa-circle").css({ color: competitor.color });
                colorTag.on("click", function () {
                  onChangeCompetitorColor(competitor);
                });

                updateCompetitor(competitor);
              }
            });

          competitorSwitch.append(competitorSwitchInput);
          secondLine.append(competitorSwitch);
        }

        {
          var competitorCenterBtn = u("<button/>")
            .addClass("btn", "btn-default", "btn-sm", "p-0", "ms-1", "me-0")
            .attr({
              type: "button",
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
              type: "button",
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
                Object.values(competitorList).map((otherCompetitor) => {
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
              type: "button",
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
              type: "button",
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
              fill: competitor.displayFullRoute
                ? "#20c997"
                : "var(--bs-body-color)",
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
            competitor.isShown ? "if-live" : "",
            "battery-indicator",
            !isLive || !competitor.isShown ? "d-none" : ""
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
            )}`,
            !competitorBatteyLevels[competitor.id] ? "text-muted" : ""
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

      var divOneUp = u(
        '<div class="card mb-1" style="background-color:transparent;"/>'
      ).append(div);

      this.el = divOneUp.nodes[0];
      this.appendChild(this.el);
    }
  }

  window.customElements.define("competitor-sidebar-el", CompetitorSidebarEl);

  function initializeMap() {
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
    locateControl = L.control.locate({
      flyTo: true,
      returnToPrevBounds: true,
      showCompass: false,
      showPopup: false,
      locateOptions: {
        watch: true,
        enableHighAccuracy: true,
      },
    });
    locateControl.addTo(map);
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

    var progressBarSlider = document.querySelector("#full_progress_bar");
    progressBarSlider.onmousedown = function (event) {
      event.preventDefault();
      document.addEventListener("mousemove", pressProgressBar);
      function onMouseUp() {
        document.removeEventListener("mouseup", onMouseUp);
        document.removeEventListener("mousemove", pressProgressBar);
      }
      document.addEventListener("mouseup", onMouseUp);
    };
    progressBarSlider.ondragstart = function (e) {
      e.preventDefault();
      return false;
    };
    progressBarSlider.addEventListener("touchmove", touchProgressBar);
  }

  function fitRasterMapLayerBounds(bounds) {
    var bLat = bounds.map((coord) => coord[0]).sort(sortingFunction);
    var bLon = bounds.map((coord) => coord[1]).sort(sortingFunction);
    var s = (bLat[0] + bLat[1]) / 2;
    var n = (bLat[2] + bLat[3]) / 2;
    var w = (bLon[0] + bLon[1]) / 2;
    var e = (bLon[2] + bLon[3]) / 2;

    var newBounds = [
      [n, e],
      [n, w],
      [s, w],
      [s, e],
    ];
    map.fitBounds(newBounds, { animate: false });
  }

  function setRasterMap(layer, fit) {
    layer.addTo(map);
    if (fit) {
      map.setBearing(layer.data.rotation, { animate: false });
      fitRasterMapLayerBounds(layer.options.bounds);
    }
    layer.setOpacity(mapOpacity);
    rasterMapLayer = layer;
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
    u("#permanent-sidebar").addClass("no-sidebar");
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
    u("#permanent-sidebar").removeClass("no-sidebar");
    sidebarShown = true;
    try {
      map.invalidateSize();
    } catch {}
  }

  function CountDown() {
    var duration = dayjs.duration(dayjs(eventStart).diff(dayjs()));
    var durationInSeconds = duration.asSeconds();
    var days = Math.floor(durationInSeconds / (24 * 3600));
    durationInSeconds -= days * (24 * 3600);
    var hours = Math.floor(durationInSeconds / 3600);
    durationInSeconds -= hours * 3600;
    var minutes = Math.floor(durationInSeconds / 60);
    durationInSeconds -= minutes * 60;
    var seconds = Math.floor(durationInSeconds);

    var daysText = dayjs.duration(2, "days").humanize().replace("2", "").trim();
    var hoursText = dayjs
      .duration(2, "hours")
      .humanize()
      .replace("2", "")
      .trim();
    var minutesText = dayjs
      .duration(2, "minutes")
      .humanize()
      .replace("2", "")
      .trim();
    var secondsText = dayjs
      .duration(2, "seconds")
      .humanize()
      .replace("2", "")
      .trim();

    return `<div class="mb-3 justify-content-center fw-bold d-flex text-uppercase">
      <div class="mx-3"><span class="fs-3">${days}</span><br/>${daysText}</div>
      <div class="mx-3"><span class="fs-3">${hours}</span><br/>${hoursText}</div>
      <div class="mx-3"><span class="fs-3">${minutes}</span><br/>${minutesText}</div>
      <div class="mx-3"><span class="fs-3">${seconds}</span><br/>${secondsText}</div>
      </div>
      <div style="font-size:0.7em;color: var(--bs-secondary)">( ${capitalizeFirstLetter(
        dayjs(eventStart).local().format("LLLL")
      )} )</div>`;
  }
  function capitalizeFirstLetter(string) {
    return string.charAt(0).toUpperCase() + string.slice(1);
  }
  (function initialize() {
    window.addEventListener("resize", onAppResize);
    initializeMap();
    reqwest({
      url: infoURL,
      withCredentials: true,
      crossOrigin: true,
      type: "json",
      success: function (response) {
        if (response.event.backdrop === "blank") {
          u("#map").css({ background: "#fff" });
        } else {
          var layer = backdropMaps?.[response.event.backdrop];
          if (layer) {
            layer.addTo(map);
            layer.nickname = response.event.backdrop;
            bgLayer = layer;
          }
        }
        var now = clock.now();
        eventStart = new Date(response.event.start_date);

        setInterval(function () {
          u("#event-start-date-value").html(CountDown());
        }, 1000);

        u("#event-start-date-value").html(CountDown());

        eventEnd = new Date(response.event.end_date);
        if (eventStart > now) {
          // show event not started modal
          try {
            map.remove();
          } catch {}
          u(".event-tool").hide();
          u("#eventLoadingModal").remove();
          u("#permanent-sidebar").remove();
          u("#export-nav-item").remove();
          hideSidebar();
          u("#map").removeClass("no-sidebar");
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
            if (clock.now() > eventStart) {
              location.reload();
            }
          }, 1e3);
        } else {
          // event if started
          u("#runners_show_button").on("click", toggleCompetitorList);
          u("#live_button")
            .on("click", onSwitchToLive)
            .text(banana.i18n("live-mode"));
          u("#replay_button")
            .on("click", onSwitchToReplay)
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
          u("#mass_start_button").on("click", function (e) {
            e.preventDefault();
            onPressResetMassStart();
          });
          u("#mass_start_text").text(banana.i18n("mass-start"));
          u("#options_show_button").on("click", displayOptions);
          u("#full_progress_bar").on("click", pressProgressBar);
          u("#share_button").on("click", shareURL);
          map.contextmenu.insertItem(
            {
              text: banana.i18n("draw-finish-line"),
              callback: drawFinishLine,
            },
            1
          );

          if (eventEnd > now) {
            // event is Live
            isLiveEvent = true;
            eventStateControl.setLive();
            u(".if-live").removeClass("d-none");
            u("#full_progress_bar").addClass("d-none");
            u("#replay_mode_buttons").hide();
            u("#replay_control_buttons").hide();
          } else {
            // event is archived
            eventStateControl.setReplay();
            u("#replay_button").addClass("d-none");
            u("#live_button")
              .off("click", onSwitchToLive)
              .text(banana.i18n("archived-event"))
              .removeClass("btn-secondary", "fst-italic")
              .addClass("btn-info", "disabled");
          }

          shortcutURL = response.event.shortcut;
          dataURL = response.data_url;
          sendInterval = response.event.send_interval;
          tailLength = response.event.tail_length;
          u("#tail-length-display").text(printTime(tailLength));

          displayAnouncement(response.announcement);
          displayMaps(response.maps, true);

          u(".main").removeClass("loading");
          u(".sidebar").removeClass("loading");
          u(".time_bar").removeClass("loading");
          u("#permanent-sidebar").removeClass("loading");
          onAppResize();
          map.invalidateSize();
          if (rasterMapLayer) {
            fitRasterMapLayerBounds(rasterMapLayer.options.bounds);
          }

          fetchCompetitorRoutes(function () {
            u("#eventLoadingModal").remove();
            if (isLiveEvent) {
              onSwitchToLive();
            } else {
              isLive = true;
              onSwitchToReplay();
            }
            onAppResize();
          });
        }
        setInterval(refreshData, 25 * 1e3);
      },
      error: function () {
        u("#eventLoadingModal").remove();
        swal({ text: "Something went wrong", title: "error", type: "error" });
      },
    });
  })();

  function onSwitchToLive(e) {
    if (e !== undefined) {
      e.preventDefault();
    }
    if (isLive) {
      return;
    }
    isLive = true;
    isRealTime = true;
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
      .off("click")
      .removeClass("btn-info", "disabled")
      .addClass("active", "fst-italic")
      .text(banana.i18n("live-mode"));
    u("#replay_button").removeClass("d-none");
    u("#real_time_button").removeClass("active");
    u("#mass_start_button").removeClass("active");
    u("#replay_mode_buttons").hide();
    u("#replay_control_buttons").hide();
    onAppResize();

    function whileLive(ts) {
      if (
        ts - routesLastFetched > fetchPositionInterval * 1e3 &&
        !isCurrentlyFetchingRoutes
      ) {
        fetchCompetitorRoutes();
      }
      currentTime =
        +clock.now() - (fetchPositionInterval + 5 + sendInterval + 5) * 1e3; // 25sec // Delay includes by the fetch interval (10s) + the cache interval (5sec) + the send interval (default 5sec) + smoothness delay (5sec)
      if (ts - prevDisplayRefresh > 100) {
        var refreshMeters = ts - prevMeterDisplayRefresh > 500;
        drawCompetitors(refreshMeters);
        prevDisplayRefresh = ts;
        if (refreshMeters) {
          prevMeterDisplayRefresh = ts;
        }
      }
      var isStillLive = eventEnd >= clock.now();
      if (!isStillLive) {
        onSwitchToReplay();
      }
      if (isLive) {
        window.requestAnimationFrame(whileLive);
      }
    }
    window.requestAnimationFrame(whileLive);
  }

  function getCompetitionStartDate(nullIfNone = false) {
    var res = +clock.now();
    var found = false;
    Object.values(competitorRoutes).forEach(function (route) {
      if (route) {
        if (res > route.getByIndex(0).timestamp) {
          res = route.getByIndex(0).timestamp;
          found = true;
        }
      }
    });
    if (nullIfNone && !found) {
      return null;
    }
    return res;
  }

  function getCompetitionEndDate() {
    var res = new Date(0);
    Object.values(competitorRoutes).forEach(function (route) {
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
    Object.values(competitorList).forEach(function (competitor) {
      var route = competitorRoutes[competitor.id];
      if (route) {
        var idx = route.getPositionsCount() - 1;
        var dur =
          route.getByIndex(idx).timestamp -
          ((customOffset
            ? competitor.custom_offset
            : +new Date(competitor.start_time)) || getCompetitionStartDate());
        res = res < dur ? dur : res;
      }
    });
    return res;
  }

  function drawFinishLine(e) {
    finishLinePoints = [];
    if (finishLinePoly) {
      map.removeLayer(finishLinePoly);
      if (rankControl) {
        map.removeControl(rankControl);
      }
      finishLinePoly = null;
      finishLineSet = false;
      rankControl = null;
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
      rankControl = null;
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
        2 +
          (!!setMassStartContextMenuItem ? 1 : 0) +
          (!!resetMassStartContextMenuItem ? 1 : 0)
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

  function getCompetitorsMinCustomOffset() {
    return competitorsMinCustomOffset;
  }

  function refreshData() {
    reqwest({
      url: infoURL,
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
        eventEnd = new Date(response.event.end_date);

        if (new Date(response.event.start_date) != eventStart) {
          var oldStart = eventStart;
          eventStart = new Date(response.event.start_date);
          // user changed the event start from past to in the future
          if (oldStart < clock.now() && eventStart > clock.now()) {
            window.location.reload();
            return;
          }
          // user changed the event start from future to in the past
          if (oldStart > clock.now() && eventStart < clock.now()) {
            window.location.reload();
            return;
          }
        }
        displayAnouncement(response.announcement);
        displayMaps(response.maps);
      },
    });
  }

  function displayAnouncement(announcement) {
    if (announcement && announcement != previousFetchAnouncement) {
      function showToast() {
        u(".text-alert-content").text(announcement);
        toastAnouncement.show();
      }
      function onHidden(e) {
        this.removeEventListener("hidden.bs.toast", onHidden);
        showToast();
      }
      var isHidden = u("#text-alert").hasClass("show");
      if (isHidden) {
        document
          .getElementById("text-alert")
          .addEventListener("hidden.bs.toast", onHidden);
        toastAnouncement.hide();
      } else {
        showToast();
      }
      previousFetchAnouncement = announcement;
    }
  }

  function displayMaps(maps, init = false) {
    if (Array.isArray(maps) && JSON.stringify(maps) !== previousFetchMapData) {
      previousFetchMapData = JSON.stringify(maps);
      var currentMapUpdated = maps.find(function (m) {
        return (
          rasterMapLayer &&
          m.id === rasterMapLayer.data.id &&
          m.modification_date !== rasterMapLayer.data.modification_date
        );
      });
      var currentMap = maps.find(function (m) {
        return rasterMapLayer && m.id === rasterMapLayer.data.id;
      });
      if (rasterMapLayer && (currentMapUpdated || maps.length <= 1)) {
        rasterMapLayer.remove();
      }
      if (maps.length) {
        var mapChoices = {};
        for (var i = 0; i < maps.length; i++) {
          var mapData = maps[i];
          mapData.title =
            !mapData.title && mapData.default
              ? '<i class="fa-solid fa-star"></i> Main Map'
              : u("<i/>").text(mapData.title).text();
          var layer = addRasterMapLayer(mapData, i);
          mapChoices[mapData.title] = layer;

          var isSingleMap = maps.length === 1;
          var isCurrentMap = currentMap?.id === mapData.id;
          var isItNewDefaultWhenCurrentDeleted = !currentMap && mapData.default;
          if (isSingleMap || isCurrentMap || isItNewDefaultWhenCurrentDeleted) {
            setRasterMap(layer, currentMapUpdated || isSingleMap || init);
          }
        }

        if (mapSelectorLayer) {
          mapSelectorLayer.remove();
        }
        if (maps.length > 1) {
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
        zoomOnRunners = init;
        u("#toggleMapSwitch").parent().parent().hide();
        mapOpacity = 1;
      }
    }
  }
  function onSwitchToReplay(e) {
    if (e !== undefined) {
      e.preventDefault();
    }
    if (!isLive) {
      return;
    }

    u(".if-live").addClass("d-none");
    u("#full_progress_bar").removeClass("d-none");
    u("#real_time_button").addClass("active");
    u("#mass_start_button").removeClass("active");

    eventStateControl.setReplay();
    u("#live_button")
      .on("click", onSwitchToLive)
      .text(banana.i18n("return-live-mode"))
      .removeClass("active", "fst-italic", "btn-info", "disabled")
      .addClass("btn-secondary");
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
        1
      );
    }
    isLive = false;
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
            getCompetitorsMinCustomOffset() + getCompetitorsMaxDuration(true);
        }
        if (isRealTime) {
          maxCTime =
            getCompetitionStartDate() +
            (Math.min(+clock.now(), getCompetitionEndDate()) -
              getCompetitionStartDate());
        }
        currentTime = Math.min(+clock.now(), currentTime, maxCTime);
        var liveTime =
          +clock.now() - (fetchPositionInterval + 5 + sendInterval + 5) * 1e3;

        if (getCompetitionStartDate(true) !== null && currentTime > liveTime) {
          onSwitchToLive();
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

      var isStillLive = isLiveEvent && eventEnd >= clock.now();
      var isBackLive = !isLiveEvent && eventEnd >= clock.now();
      if (!isStillLive) {
        u("#live_button")
          .off("click")
          .text(banana.i18n("archived-event"))
          .removeClass("btn-secondary", "fst-italic", "active")
          .addClass("btn-info", "disabled");
        isLiveEvent = false;
      }
      if (isBackLive) {
        u("#live_button")
          .on("click", onSwitchToLive)
          .text(banana.i18n("return-live-mode"))
          .removeClass("active", "fst-italic", "btn-info", "disabled")
          .addClass("btn-secondary");
        isLiveEvent = true;
      }

      if (!isLive) {
        window.requestAnimationFrame(whileReplay);
      }
    }
    whileReplay(performance.now());
  }

  this.getTailLength = function () {
    return tailLength;
  };

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
        u("#permanent-sidebar").addClass("no-sidebar");
        u("#permanent-sidebar .btn").removeClass("active");
      } else if (u("#map").hasClass("no-sidebar") && width > 576) {
        u("#map").removeClass("no-sidebar");
        u("#permanent-sidebar").removeClass("no-sidebar");
        if (optionDisplayed) {
          u("#options_show_button").addClass("active");
        } else {
          u("#runners_show_button").addClass("active");
        }
      }
    }
  }

  function onLayerChange(event) {
    map.setBearing(event.layer.data.rotation, { animate: false });
    fitRasterMapLayerBounds(event.layer.options.bounds);
    rasterMapLayer = event.layer;
    rasterMapLayer.setOpacity(mapOpacity);
  }

  function updateCompetitor(newData) {
    if (Object.keys(competitorList).includes(newData.id)) {
      Object.keys(newData).forEach(function (k) {
        competitorList[newData.id][k] = newData[k];
      });
    } else {
      competitorList[newData.id] = newData;
    }
  }

  function updateCompetitorList(newList) {
    newList.forEach(updateCompetitor);
  }

  function displayCompetitorList(force) {
    if (!force && optionDisplayed) {
      return;
    }
    optionDisplayed = false;
    var scrollTopDiv = u("#competitorList").first()?.scrollTop;
    var listDiv = u("<div/>");
    listDiv.addClass("mt-1");
    listDiv.attr({ id: "competitorList", "data-bs-theme": getCurrentTheme() });

    Object.values(competitorList).forEach(function (competitor, i) {
      if (
        searchText === null ||
        searchText === "" ||
        competitor.name.toLowerCase().search(searchText) != -1
      ) {
        var div = u(
          `<competitor-sidebar-el index="${i}"competitor-id="${competitor.id}"/>`
        );
        listDiv.append(div);
      }
    });

    if (Object.keys(competitorList).length === 0) {
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
      var mainDiv = u(
        '<div id="competitorSidebar" class="d-flex flex-column"/>'
      );
      var topDiv = u("<div/>");
      var searchBar = u("<form/>").addClass("row g-0 flex-nowrap");
      if (Object.keys(competitorList).length) {
        var toggleAllContent = u("<div/>")
          .addClass(
            "form-group",
            "form-check",
            "form-switch",
            "d-inline-block",
            "ms-1",
            "col-auto",
            "pt-2",
            "me-0",
            "pe-0"
          )
          .attr({
            "aria-label": "toggle all competitors",
          });
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
              Object.values(competitorList).forEach(function (competitor) {
                if (!competitor.isShown) {
                  competitor.isShown = true;
                }
                updateCompetitor(competitor);
              });
            } else {
              Object.values(competitorList).forEach(function (competitor) {
                competitor.isShown = false;
                competitor.focused = false;
                competitor.highlighted = false;
                competitor.displayFullRoute = false;
                ["mapMarker", "nameMarker", "tail"].forEach(function (
                  layerName
                ) {
                  competitor[layerName]?.remove();
                  competitor[layerName] = null;
                });
                updateCompetitor(competitor);
              });
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
    if (Object.keys(competitorList).length == 0) {
      listDiv.addClass("without-competitor");
    }
    if (scrollTopDiv) {
      listDiv.nodes[0].scrollTop = scrollTopDiv;
    }
    u(".tooltip").remove();
    const tooltipEls = u("#competitorSidebar").find(
      '[data-bs-toggle="tooltip"]'
    );
    tooltipEls.map((el) => new bootstrap.Tooltip(el, { trigger: "hover" }));
  }

  function setCustomStart(latlng) {
    competitorsMinCustomOffset = +clock.now();
    Object.values(competitorList).forEach(function (competitor) {
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
        competitorsMinCustomOffset = Math.min(
          minDistT,
          competitorsMinCustomOffset
        );
      }
    });
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
    perc = Math.max(Math.min(100, perc), 0);
    if (isRealTime) {
      currentTime =
        getCompetitionStartDate() +
        (Math.min(clock.now(), getCompetitionEndDate()) -
          getCompetitionStartDate()) *
          perc;
    } else if (isCustomStart) {
      currentTime =
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

  function centerMap(e) {
    map.panTo(e.latlng);
  }

  function shareURL(e) {
    e.preventDefault();
    var shareData = {
      title: u('meta[property="og:title"]').attr("content"),
      text: u('meta[property="og:description"]').attr("content"),
      url: shortcutURL,
    };
    try {
      navigator
        .share(shareData)
        .then(function () {})
        .catch(function () {});
    } catch (err) {}
  }

  function onPressCustomMassStart(e) {
    if (!isLive) {
      isRealTime = false;
      isCustomStart = true;

      u("#real_time_button").removeClass("active");
      u("#mass_start_button").removeClass("active");
      setCustomStart(e.latlng);
      currentTime = getCompetitorsMinCustomOffset();
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

  function touchProgressBar(e) {
    var touchLocation = e.targetTouches[0];
    var perc =
      (touchLocation.pageX -
        document.getElementById("full_progress_bar").offsetLeft) /
      u("#full_progress_bar").size().width;
    e.preventDefault();
    onMoveProgressBar(perc);
  }

  function fetchCompetitorRoutes(cb) {
    isCurrentlyFetchingRoutes = true;
    reqwest({
      url: dataURL,
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

  function zoomOnCompetitor(competitor) {
    if (!competitor.isShown || competitor.focusing) {
      return;
    }
    competitor.focusing = true;
    var route = competitorRoutes[competitor.id];
    if (!route) {
      competitor.focusing = false;
      return;
    }
    var timeT = currentTime;
    if (!isRealTime) {
      if (isCustomStart) {
        timeT += competitor.custom_offset - getCompetitionStartDate();
      } else {
        timeT += +new Date(competitor.start_time) - getCompetitionStartDate();
      }
    }
    var loc = route.getByTime(timeT);
    map.setView([loc.coords.latitude, loc.coords.longitude], map.getZoom(), {
      animate: true,
    });
    setTimeout(function () {
      competitor.focusing = false;
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
    u("#colorModalLabel").text(
      banana.i18n("select-color-for", competitor.name)
    );
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
    optionsSidebar.attr({
      id: "optionsSidebar",
      "data-bs-theme": getCurrentTheme(),
    });

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
        .html(
          `<i class="fa-solid fa-language"></i> ${banana.i18n("language")}`
        );

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

    if (rasterMapLayer) {
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
          rasterMapLayer?.setOpacity(mapOpacity);
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
          if (bgLayer) {
            bgLayer.remove();
            bgLayer = null;
          }
          if (e.target.value === "blank") {
            u("#map").css({ background: "#fff" });
          } else {
            u("#map").css({ background: "#ddd" });
            var layer = cloneLayer(backdropMaps[e.target.value]);
            layer.nickname = e.target.value;
            layer.setZIndex(-1);
            layer.addTo(map);
            bgLayer = layer;
          }
        });

      var blankOption = u("<option/>");
      blankOption.attr({ value: "blank" });
      blankOption.text("Blank");
      if (!bgLayer) {
        blankOption.attr({ selected: true });
      }
      mapSelector.append(blankOption);

      Object.entries(backgroundMapTitles).forEach(function (kv) {
        var option = u("<option/>");
        option.attr({ value: kv[0] });
        option.text(kv[1]);
        if (bgLayer?.nickname === kv[0]) {
          option.attr({ selected: true });
        }
        mapSelector.append(option);
      });

      bgMapWidget.append(widgetTitle).append(mapSelector);

      optionsSidebar.append(bgMapWidget);
    }

    if (shortcutURL) {
      var qr = new QRious();
      qr.set({
        background: "#f5f5f5",
        foreground: "black",
        level: "L",
        value: shortcutURL,
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
        .attr({ href: shortcutURL })
        .text(shortcutURL.replace(/^https?:\/\//, ""));

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
    if (isCustomStart) {
      viewedTime -= getCompetitorsMinCustomOffset();
    } else {
      viewedTime -= getCompetitionStartDate();
    }
    return viewedTime;
  }
  this.getRelativeTime = getRelativeTime;

  function getProgressBarText(currentTime, bg = false, date = false) {
    var result = "";
    if (bg && isLive) {
      return "";
    }
    var viewedTime = currentTime;
    if (!isRealTime) {
      if (currentTime === 0) {
        return "00:00:00";
      }
      if (isCustomStart) {
        viewedTime -= getCompetitorsMinCustomOffset();
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
  this.getProgressBarText = getProgressBarText;

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
      elemCenter.y >
      (document.documentElement.clientHeight || window.innerHeight)
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
      perc = isLive
        ? 100
        : ((currentTime - getCompetitionStartDate()) /
            (Math.min(+clock.now(), getCompetitionEndDate()) -
              getCompetitionStartDate())) *
          100;
    } else {
      if (isCustomStart) {
        perc =
          ((currentTime - getCompetitorsMinCustomOffset()) /
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

    Object.values(competitorList).forEach(function (competitor) {
      if (!competitor.isShown) {
        return;
      }
      var route = competitorRoutes[competitor.id];
      if (route !== undefined) {
        var viewedTime = currentTime;
        if (!isLive && !isRealTime && !isCustomStart && competitor.start_time) {
          viewedTime +=
            new Date(competitor.start_time) - getCompetitionStartDate();
        } else if (
          !isLive &&
          !isRealTime &&
          isCustomStart &&
          competitor.custom_offset
        ) {
          viewedTime += Math.max(
            0,
            competitor.custom_offset - getCompetitorsMinCustomOffset()
          );
        }
        var loc = route.getByTime(viewedTime);
        var hasRecentPoints = route.hasPointInInterval(
          viewedTime - (sendInterval * 4 + fetchPositionInterval) * 1e3, //kayak
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
          viewedTime > route.getByIndex(0).timestamp && !hasRecentPoints;
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
                      !isLive &&
                      !isRealTime &&
                      !isCustomStart &&
                      competitor.start_time
                    ) {
                      competitorTime -=
                        new Date(competitor.start_time) -
                        getCompetitionStartDate();
                    }
                    if (
                      !isLive &&
                      !isRealTime &&
                      isCustomStart &&
                      competitor.custom_offset
                    ) {
                      competitorTime -= Math.max(
                        0,
                        competitor.custom_offset -
                          getCompetitorsMinCustomOffset()
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
                      !isLive &&
                      !isRealTime &&
                      !isCustomStart &&
                      competitor.start_time
                    ) {
                      competitorTime -=
                        new Date(competitor.start_time) -
                        getCompetitionStartDate();
                    }
                    if (
                      !isLive &&
                      !isRealTime &&
                      isCustomStart &&
                      competitor.custom_offset
                    ) {
                      competitorTime -= Math.max(
                        0,
                        competitor.custom_offset -
                          getCompetitorsMinCustomOffset()
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
    });

    // Create cluster
    if (showClusters) {
      var competitorsWithMarker = [];
      var competitorsLocations = [];
      Object.values(competitorList).forEach(function (competitor) {
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
      });
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
}

(function () {
  if (!navigator.canShare) {
    document.getElementById("share_buttons").remove();
  }
  var queryString = window.location.search;
  var urlParams = new URLSearchParams(queryString);

  var urlLanguage = getLangIfSupported(urlParams.get("lang"));
  var storedLanguage = getLangIfSupported(window.localStorage.getItem("lang"));
  var browserLanguage = getLangIfSupported(navigator.language.slice(0, 2));
  locale = urlLanguage || storedLanguage || browserLanguage || "en";
  dayjs.locale(locale);
  banana = new Banana();
  updateText().then(function () {
    u("#event-start-date-text").text(banana.i18n("event-start-date-text"));
    u("#heads-up-text").text(banana.i18n("heads-up-text"));
    u("#export-text").text(banana.i18n("export"));
    u("#loading-text").text(banana.i18n("loading-text"));
    u(".cancel-text").text(banana.i18n("cancel"));
    u(".save-text").text(banana.i18n("save"));
    u("#event-not-started-text").text(banana.i18n("event-not-started-text"));
    u("#club-events-link-text").text(
      banana.i18n("club-events-link-text", window.local.clubName)
    );
    u("#real_time_text").text(banana.i18n("real-time"));

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
    myEvent = new RCEvent(window.local.eventUrl, window.local.serverClockUrl);
  });
})();
