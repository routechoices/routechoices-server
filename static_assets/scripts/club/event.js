function RCEvent(infoURL, clockURL) {
  let bgLayer = null;
  const clock = ServerClock({ url: clockURL, burstSize: 1 });
  setTimeout(clock.stopRefreshes, 1000);
  let eventStart = null;
  let eventEnd = null;
  let map = null;
  let locateControl;
  let eventStateControl;
  let coordsControl;
  let panControl;
  let zoomControl;
  let rotateControl;
  let scaleControl;
  let runnerIconScale = 1;
  let isLive = false;
  let isLiveEvent = false;
  let shortcutURL = "";
  let dataURL;
  let sendInterval = 5;
  let tailLength = 60;
  let previousFetchMapData = null;
  let previousFetchAnouncement = null;
  let zoomOnRunners = false;
  let rasterMapLayer;
  let mapOpacity = 1;
  const toastAnouncement = new bootstrap.Toast(
    document.getElementById("text-alert"),
    {
      animation: true,
      autohide: false,
    }
  );
  toastAnouncement.hide();

  let isRealTime = true;
  let isCustomStart = false;
  let competitorList = {};
  let competitorRoutes = {};
  let competitorBatteyLevels = {};
  let routesLastFetched = -Infinity;
  let fetchPositionInterval = 10;
  let playbackRate = 8;
  let playbackPaused = true;
  let prevDisplayRefresh = 0;
  let prevMeterDisplayRefresh = 0;
  let isCurrentlyFetchingRoutes = false;
  let currentTime = 0;
  let optionDisplayed = false;
  let searchText = null;
  let resetMassStartContextMenuItem = null;
  let setMassStartContextMenuItem = null;
  let clusters = {};
  let splitLineCount = 0;
  let splitTimes = [];
  let startLineCrosses = [];
  let splitLinesPoints = [];
  let splitLinesLine = [];
  let splitLinesLabel = [];
  let removeSplitLinesContextMenuItem = [];
  let rankingFromLap = 1;
  let rankingFromSplit = null;
  let rankingToLap = 1;
  let rankingToSplit = null;
  let showClusters = false;
  let showControls = false;
  const colorModal = new bootstrap.Modal(document.getElementById("colorModal"));
  let mapSelectorLayer = null;
  let sidebarShown = true;
  let isMapMoving = false;
  let intersectionCheckZoom = 18;
  let showUserLocation = false;
  let showAll = true;
  let rankControl = null;
  let competitorsMinCustomOffset = null;

  L.Control.Ranking = L.Control.extend({
    onAdd: function () {
      const back = L.DomUtil.create(
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

      u(back).prepend(
        '<div class="result-list-title">' +
          '<h6><i class="fa-solid fa-trophy"></i> ' +
          banana.i18n("ranking") +
          '<button class="btn float-end m-0 p-0" type="button" id="dl-ranking-btn"><i class="fa-solid fa-download"></i></button>' +
          "</h6>" +
          "</div>" +
          '<div class="result-split-selectors"></div>'
      );

      return back;
    },

    setSplitSelectors: function () {
      const out =
        '<div class="d-flex flex-row">' +
        '<div class="me-1">' +
        "<label>" +
        banana.i18n("from") +
        "</label>" +
        '<select class="form-control" style="font-size: 0.5rem;width: 41px" id="from-split">' +
        `<option value="" ${
          rankingFromSplit === null ? "selected" : ""
        }>&#x25B7;</option>` +
        splitLinesLine
          .map(function (a, i) {
            return !!a
              ? `<option value="${i}" ${
                  i === rankingFromSplit ? "selected" : ""
                }>${i + 1}</option>`
              : "";
          })
          .filter(function (a) {
            return !!a;
          })
          .join("") +
        "</select>" +
        "</div>" +
        '<div class="me-1">' +
        "<label>" +
        banana.i18n("lap") +
        "</label>" +
        `<input type="number" min="1" id="from-lap" step="1" value="${rankingFromLap}" class="d-block cross-count form-control" style="font-size: 0.5rem;width: 50px">` +
        "</div>" +
        '<div class="me-1">' +
        "<label>" +
        banana.i18n("to") +
        "</label>" +
        '<select class="form-control" style="font-size: 0.5rem;width: 41px" id="to-split">' +
        splitLinesLine
          .map(function (a, i) {
            return !!a
              ? `<option value="${i}" ${
                  i === rankingToSplit ? "selected" : ""
                }>${i + 1}</option>`
              : "";
          })
          .filter(function (a) {
            return !!a;
          })
          .join("") +
        "</select>" +
        "</div>" +
        '<div class="m-0">' +
        "<label>" +
        banana.i18n("lap") +
        "</label>" +
        `<input type="number" min="1" id="to-lap" step="1" value="${rankingToLap}" class="d-block cross-count form-control" style="font-size: 0.5rem;width: 50px">` +
        "</div>" +
        "</div>";
      u(".result-split-selectors").html(out);

      u("#from-split").on("change", function (e) {
        if (e.target.value !== "") {
          rankingFromSplit = parseInt(e.target.value);
          u("#from-lap").val(1);
        } else {
          rankingFromSplit = null;
        }
        u("#from-lap").val(1).trigger("change");
      });
      u("#from-lap").on("change", function (e) {
        if (rankingFromSplit == null) {
          e.target.value = 1;
        }
        rankingFromLap = Math.max(1, parseInt(e.target.value));
      });
      u("#to-split").on("change", function (e) {
        if (e.target.value !== "") {
          rankingToSplit = parseInt(e.target.value);
        } else {
          rankingToSplit = null;
        }
        u("#to-lap").val(1).trigger("change");
      });
      u("#to-lap").on("change", function (e) {
        rankingToLap = Math.max(1, parseInt(e.target.value));
      });
      u("#from-lap").trigger("change");
      u("#to-lap").trigger("change");
    },

    setValues: function (ranking) {
      const el = u(".leaflet-control-ranking").find(".result-name-list");
      const innerOut = u('<div class="result-name-list"/>');
      if (ranking.length > 0) {
        ranking.sort(function (a, b) {
          return a.time - b.time;
        });
      }
      const relativeTime = rankingFromSplit == null;
      ranking.forEach(function (c, i) {
        innerOut.append(
          '<div class="text-nowrap overflow-hidden text-truncate" style="clear: both; width: 200px;"><span class="text-nowrap d-inline-block float-start overflow-hidden text-truncate" style="width: 135px;">' +
            (i + 1) +
            ' <span style="color: ' +
            c.competitor.color +
            '">&#11044;</span> ' +
            u("<span/>").text(c.competitor.name).html() +
            '</span><span class="text-nowrap overflow-hidden d-inline-block float-end" style="width: 55px; font-feature-settings: tnum; font-variant-numeric: tabular-nums lining-nums; margin-right: 10px;" title="' +
            getProgressBarText(c.time, false, false, relativeTime) +
            '">' +
            getProgressBarText(c.time, false, false, relativeTime) +
            "</span></div>"
        );
      });
      if (innerOut.html() === "") {
        innerOut.append("<div>-</div>");
      }
      if (el.html() !== innerOut.html()) {
        el.html(innerOut.html());
      }
      u(".leaflet-control-ranking #dl-ranking-btn").off("click");
      u(".leaflet-control-ranking #dl-ranking-btn").on("click", function () {
        let out = "";
        ranking.forEach(function (c, i) {
          out +=
            c.competitor.name +
            ";" +
            myEvent.getProgressBarText(c.time, false, false, relativeTime) +
            "\n";
        });
        const element = document.createElement("a");
        element.setAttribute(
          "href",
          "data:text/plain;charset=utf-8," + encodeURIComponent(out)
        );
        element.setAttribute("download", "result.csv");
        element.style.display = "none";
        document.body.appendChild(element);
        element.click();
        document.body.removeChild(element);
      });
    },

    onRemove: function (map) {
      u(".leaflet-control-ranking").remove();
      u(".tmp").remove();
    },
  });

  L.control.ranking = function (opts) {
    return new L.Control.Ranking(opts);
  };

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
      const div = u("<div/>");
      div.addClass("card-body", "px-1", "pt-1", "pb-0", "competitor-card");
      {
        const firstLine = u("<div/>")
          .addClass("text-nowrap", "text-truncate", "overflow-hidden")
          .css({ lineHeight: "1.13rem" });

        const colorTag = u("<span/>")
          .addClass("color-tag", "me-1")
          .css({ cursor: "pointer" });

        if (competitor.isShown) {
          colorTag.on("click", function () {
            onChangeCompetitorColor(competitor);
          });
        }

        const colorTagIcon = u("<i/>")
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

        const nameDiv = u("<span/>")
          .addClass("overflow-hidden", "ps-0", "text-truncate", "fw-bold")
          .text(competitor.name);

        colorTag.append(colorTagIcon);
        firstLine.append(colorTag);
        firstLine.append(nameDiv);
        div.append(firstLine);
      }
      {
        const secondLine = u("<div/>").addClass(
          "text-nowrap",
          "text-truncate",
          "overflow-hidden",
          "ps-0",
          competitor.isShown ? "route-displayed" : "route-not-displayed"
        );

        {
          const competitorSwitch = u("<div/>")
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

          const competitorSwitchInput = u("<input/>")
            .addClass("form-check-input", "competitor-switch")
            .css({ boxShadow: "none" })
            .attr({
              type: "checkbox",
              checked: !!competitor.isShown,
            })
            .on("click", function (e) {
              const commonDiv = u(this).parent().parent();
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

                const colorTag = commonDiv.parent().find(".color-tag");
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

                const colorTag = commonDiv.parent().find(".color-tag");
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
          const competitorCenterBtn = u("<button/>")
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

          const competitorCenterIcon = u("<i/>").addClass(
            "fa-solid",
            "fa-location-dot"
          );

          competitorCenterBtn.append(competitorCenterIcon);
          secondLine.append(competitorCenterBtn);
        }

        {
          const competitorFollowBtn = u("<button/>")
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

          const competitorFollowBtnIcon = u("<i/>").addClass(
            "fa-solid",
            "fa-crosshairs"
          );

          competitorFollowBtn.append(competitorFollowBtnIcon);
          secondLine.append(competitorFollowBtn);
        }

        {
          const competitorHighlightBtn = u("<button/>")
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

          const competitorHighlightIcon = u("<i/>").addClass(
            "fa-solid",
            "fa-highlighter"
          );

          competitorHighlightBtn.append(competitorHighlightIcon);
          secondLine.append(competitorHighlightBtn);
        }

        {
          const competitorFullRouteBtn = u("<button/>")
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

          const competitorFullRouteBtnIcon = u("<svg/>")
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
          const batteryLevelDiv = u("<div/>").addClass(
            "float-end",
            "d-inline-blockv",
            "text-end",
            competitor.isShown ? "if-live" : "",
            "battery-indicator",
            !isLive || !competitor.isShown ? "d-none" : ""
          );

          const batterySpan = u("<span/>").attr({
            "data-bs-toggle": "tooltip",
            "data-bs-custom-class": "higher-z-index",
            "data-bs-title":
              competitorBatteyLevels[competitor.id] !== null
                ? competitorBatteyLevels[competitor.id] + "%"
                : banana.i18n("unknown"),
          });

          const batteryIcon = u("<i/>").addClass(
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
          const metersDiv = u("<div/>")
            .addClass("float-end d-inline-block text-end")
            .css({ lineHeight: "10px" });
          const speedometer = u("<span/>")
            .addClass("speedometer")
            .text(!competitor.isShown ? "" : competitor.speedometerValue || "");
          const odometer = u("<span/>")
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

      const divOneUp = u(
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
        "-",
      ],
    });

    map.on("contextmenu.show", function (e) {
      console.log(map.contextmenu);
      map.contextmenu.addItem({
        text: e.latlng.lat.toFixed(5) + ", " + e.latlng.lng.toFixed(5),
        callback: () => {
          window.open(
            "https://www.openstreetmap.org/?mlat=" +
              e.latlng.lat +
              "&mlon=" +
              e.latlng.lng
          );
        },
      });
    });
    map.on("contextmenu.hide", function (e) {
      map.contextmenu.removeItem(map.contextmenu._items.length - 1);
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

    const progressBarSlider = document.querySelector("#full_progress_bar");
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
    const bLat = bounds.map((coord) => coord[0]).sort(sortingFunction);
    const bLon = bounds.map((coord) => coord[1]).sort(sortingFunction);
    const s = (bLat[0] + bLat[1]) / 2;
    const n = (bLat[2] + bLat[3]) / 2;
    const w = (bLon[0] + bLon[1]) / 2;
    const e = (bLon[2] + bLon[3]) / 2;

    const newBounds = [
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
    const duration = dayjs.duration(dayjs(eventStart).diff(dayjs()));
    let durationInSeconds = Math.max(duration.asSeconds(), 0);
    const days = Math.floor(durationInSeconds / (24 * 3600));
    durationInSeconds -= days * (24 * 3600);
    const hours = Math.floor(durationInSeconds / 3600);
    durationInSeconds -= hours * 3600;
    const minutes = Math.floor(durationInSeconds / 60);
    durationInSeconds -= minutes * 60;
    const seconds = Math.floor(durationInSeconds);

    const daysText = dayjs
      .duration(2, "days")
      .humanize()
      .replace("2", "")
      .trim();
    const hoursText = dayjs
      .duration(2, "hours")
      .humanize()
      .replace("2", "")
      .trim();
    const minutesText = dayjs
      .duration(2, "minutes")
      .humanize()
      .replace("2", "")
      .trim();
    const secondsText = dayjs
      .duration(2, "seconds")
      .humanize()
      .replace("2", "")
      .trim();

    return `<div class="mb-3 justify-content-center fw-bold d-flex text-uppercase">
      <div class="me-2"><span class="fs-3 cd-nb">${days}</span><br/>${daysText}</div>
      <div class="ms-3 me-2"><span class="fs-3 cd-nb">${hours}</span><br/>${hoursText}</div>
      <div class="ms-3 me-2"><span class="fs-3 cd-nb">${minutes}</span><br/>${minutesText}</div>
      <div class="ms-3"><span class="fs-3 cd-nb">${seconds}</span><br/>${secondsText}</div>
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
    window.addEventListener("fullscreenchange", function () {
      onAppResize();
      if (document.fullscreenElement != null) {
        u("#fullscreenSwitch > .fa-expand")
          .addClass("fa-compress")
          .removeClass("fa-expand");
      } else {
        u("#fullscreenSwitch > .fa-compress")
          .addClass("fa-expand")
          .removeClass("fa-compress");
      }
    });

    function toggleFullscreen() {
      if (document.fullscreenElement != null) {
        document.exitFullscreen();
      } else {
        const elem = document.getElementById("main-div");
        if (elem.requestFullscreen) {
          elem.requestFullscreen();
        } else if (elem.webkitRequestFullscreen) {
          /* Safari */
          elem.webkitRequestFullscreen();
        } else if (elem.msRequestFullscreen) {
          /* IE11 */
          elem.msRequestFullscreen();
        }
      }
    }

    document
      .getElementById("fullscreenSwitch")
      ?.addEventListener("click", toggleFullscreen);

    initializeMap();
    fetch(infoURL, {
      method: "GET",
      credentials: "include",
      mode: "cors",
    })
      .then((r) => r.json())
      .then(function (response) {
        if (response.event.backdrop === "blank") {
          u("#map").css({ background: "#fff" });
        } else {
          const layer = backdropMaps?.[response.event.backdrop];
          if (layer) {
            layer.addTo(map);
            layer.nickname = response.event.backdrop;
            bgLayer = layer;
          }
        }
        const now = clock.now();
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
          const preRaceModal = new bootstrap.Modal(
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
            if (clock.now() >= eventStart) {
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
          u("#full_progress_bar").parent().on("click", pressProgressBar);
          u("#share_button").on("click", shareURL);
          map.contextmenu.insertItem(
            {
              text: banana.i18n("draw-split-line"),
              callback: drawSplitLine,
            },
            1
          );

          if (eventEnd > now) {
            // event is Live
            isLiveEvent = true;
            eventStateControl.setLive();
            u(".if-live").removeClass("d-none");
            u("#full_progress_bar").parent().addClass("d-none");
            u("#replay_mode_buttons").hide();
            u("#replay_control_buttons").hide();
          } else {
            // event is archived
            eventStateControl.setReplay();
            u("#replay_button").addClass("d-none");
            u("#live_button")
              .off("click", onSwitchToLive)
              .text(banana.i18n("archived-event"))
              .removeClass("btn-secondary")
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
      })
      .catch(function () {
        u("#eventLoadingModal").remove();
        swal({ text: "Something went wrong", title: "error", type: "error" });
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
    u("#full_progress_bar").parent().addClass("d-none");

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
      .addClass("d-none");
    u("#replay_button").removeClass("d-none");
    u("#real_time_button").removeClass("active");
    u("#mass_start_button").removeClass("active");
    u("#replay_mode_buttons").hide();
    u("#replay_control_buttons").hide();
    onAppResize();

    function renderLive(ts) {
      if (
        ts - routesLastFetched > fetchPositionInterval * 1e3 &&
        !isCurrentlyFetchingRoutes
      ) {
        fetchCompetitorRoutes();
      }
      currentTime =
        +clock.now() - (fetchPositionInterval + 5 + sendInterval + 5) * 1e3; // 25sec // Delay includes by the fetch interval (10s) + the cache interval (5sec) + the send interval (default 5sec) + smoothness delay (5sec)
      if (ts - prevDisplayRefresh > 100) {
        const mustRefreshMeters = ts - prevMeterDisplayRefresh > 500;
        drawCompetitors(mustRefreshMeters);
        prevDisplayRefresh = ts;
        if (mustRefreshMeters) {
          prevMeterDisplayRefresh = ts;
        }
      }
      const isStillLive = eventEnd >= clock.now();
      if (!isStillLive) {
        onSwitchToReplay();
      }
    }

    function whileLive(ts) {
      renderLive(ts);
      if (isLive) {
        window.requestAnimationFrame(whileLive);
      }
    }
    window.requestAnimationFrame(whileLive);
  }

  function getCompetitionStartDate(nullIfNone = false) {
    let res = +clock.now();
    let found = false;
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
    let res = new Date(0);
    Object.values(competitorRoutes).forEach(function (route) {
      if (route) {
        const idx = route.getPositionsCount() - 1;
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
    let res = 0;
    Object.values(competitorList).forEach(function (competitor) {
      const route = competitorRoutes[competitor.id];
      if (route) {
        const idx = route.getPositionsCount() - 1;
        const dur =
          route.getByIndex(idx).timestamp -
          ((customOffset
            ? competitor.custom_offset
            : +new Date(competitor.start_time)) || getCompetitionStartDate());
        res = res < dur ? dur : res;
      }
    });
    return res;
  }

  function drawSplitLine(e) {
    splitLinesPoints[splitLineCount] = [];
    if (splitLinesLine[splitLineCount]) {
      map.removeLayer(splitLinesLine[splitLineCount]);
      splitLinesLine[splitLineCount] = null;
    }
    splitLinesPoints[splitLineCount].push(e.latlng);
    map.on("click", drawSplitLineEnd);
    map.on("mousemove", drawSplitLineTmp);
  }

  function removeSplitLine(n) {
    if (splitLinesLine[n]) {
      map.removeLayer(splitLinesLine[n]);
      splitLinesLine[n] = null;
    }
    if (splitLinesLabel[n]) {
      map.removeLayer(splitLinesLabel[n]);
      splitLinesLabel[n] = null;
    }
    map.contextmenu.removeItem(removeSplitLinesContextMenuItem[n]);
    removeSplitLinesContextMenuItem[n] = null;

    rankControl.setSplitSelectors();
    if (
      !removeSplitLinesContextMenuItem.find(function (a) {
        return !!a;
      })
    ) {
      map.removeControl(rankControl);
      rankControl = null;
      rankingFromSplit = null;
      rankingToSplit = null;
    }
  }

  function drawSplitLineEnd(e) {
    if (splitLinesLine[splitLineCount]) {
      map.removeLayer(splitLinesLine[splitLineCount]);
    }
    if (splitLinesLabel[splitLineCount]) {
      map.removeLayer(splitLinesLabel[splitLineCount]);
    }

    splitLinesPoints[splitLineCount][1] = e.latlng;
    splitLinesLine[splitLineCount] = L.polyline(
      splitLinesPoints[splitLineCount],
      { color: "purple" }
    );
    const splitLineIcon = getSplitLineMarker("" + (splitLineCount + 1));
    const coordinates = splitLinesPoints[splitLineCount].sort(function (a, b) {
      return a.lat - b.lat;
    })[0];
    splitLinesLabel[splitLineCount] = L.marker(coordinates, {
      icon: splitLineIcon,
    });

    map.addLayer(splitLinesLine[splitLineCount]);
    map.addLayer(splitLinesLabel[splitLineCount]);

    map.off("click", drawSplitLineEnd);
    map.off("mousemove", drawSplitLineTmp);
    removeSplitLinesContextMenuItem.push(
      map.contextmenu.insertItem(
        {
          text: banana.i18n("remove-split-line", splitLineCount + 1),
          callback: (function (n) {
            return function () {
              removeSplitLine(n);
            };
          })(splitLineCount),
        },
        2 +
          (!!setMassStartContextMenuItem ? 1 : 0) +
          (!!resetMassStartContextMenuItem ? 1 : 0) +
          removeSplitLinesContextMenuItem.filter(function (a) {
            return !!a;
          }).length
      )
    );

    if (!rankControl) {
      rankingFromSplit = null;
      rankingToSplit = splitLineCount;
      rankControl = L.control.ranking({ position: "topright" });
      map.addControl(rankControl);
    }
    rankControl.setSplitSelectors();
    splitLineCount = splitLineCount + 1;
  }

  function drawSplitLineTmp(e) {
    splitLinesPoints[splitLineCount][1] = e.latlng;
    if (!splitLinesLine[splitLineCount]) {
      splitLinesLine[splitLineCount] = L.polyline(
        splitLinesPoints[splitLineCount],
        { color: "purple" }
      );
      map.addLayer(splitLinesLine[splitLineCount]);
    } else {
      splitLinesLine[splitLineCount].setLatLngs(
        splitLinesPoints[splitLineCount]
      );
    }
  }

  function getCompetitorsMinCustomOffset() {
    return competitorsMinCustomOffset;
  }

  function refreshData() {
    fetch(infoURL, {
      method: "GET",
      credentials: "include",
      mode: "cors",
    })
      .then((r) => r.json())
      .then(function (response) {
        if (response.error) {
          if (response.error === "No event match this id") {
            window.location.reload();
          }
          return;
        }
        eventEnd = new Date(response.event.end_date);

        if (new Date(response.event.start_date) != eventStart) {
          const oldStart = eventStart;
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
      const isHidden = u("#text-alert").hasClass("show");
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
      const currentMapUpdated = maps.find(function (m) {
        return (
          rasterMapLayer &&
          m.id === rasterMapLayer.data.id &&
          m.modification_date !== rasterMapLayer.data.modification_date
        );
      });
      const currentMap = maps.find(function (m) {
        return rasterMapLayer && m.id === rasterMapLayer.data.id;
      });
      if (rasterMapLayer && (currentMapUpdated || maps.length <= 1)) {
        rasterMapLayer.remove();
      }
      if (maps.length) {
        const mapChoices = {};
        for (let i = 0; i < maps.length; i++) {
          const mapData = maps[i];
          mapData.title =
            !mapData.title && mapData.default
              ? '<i class="fa-solid fa-star"></i> Main Map'
              : u("<i/>").text(mapData.title).text();
          const layer = addRasterMapLayer(mapData, i);
          mapChoices[mapData.title] = layer;

          const isSingleMap = maps.length === 1;
          const isCurrentMap = currentMap?.id === mapData.id;
          const isItNewDefaultWhenCurrentDeleted =
            !currentMap && mapData.default;
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
    u("#full_progress_bar").parent().removeClass("d-none");
    u("#real_time_button").addClass("active");
    u("#mass_start_button").removeClass("active");

    eventStateControl.setReplay();
    u("#live_button")
      .on("click", onSwitchToLive)
      .text(banana.i18n("return-live-mode"))
      .removeClass("active", "btn-info", "disabled", "d-none")
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

    function renderReplay(ts) {
      if (
        isLiveEvent &&
        ts - routesLastFetched > fetchPositionInterval * 1e3 &&
        !isCurrentlyFetchingRoutes
      ) {
        fetchCompetitorRoutes();
      }
      const actualPlaybackRate = playbackPaused ? 0 : playbackRate;
      if (getCompetitionStartDate(true) === null) {
        currentTime = 0;
        maxCTime = 0;
      } else {
        currentTime = Math.max(
          getCompetitionStartDate(),
          prevShownTime + (ts - prevDisplayRefresh) * actualPlaybackRate
        );
        let maxCTime = getCompetitionStartDate() + getCompetitorsMaxDuration();
        if (isCustomStart) {
          maxCTime =
            getCompetitorsMinCustomOffset() + getCompetitorsMaxDuration(true);
        } else {
          maxCTime = getCompetitionStartDate() + getCompetitorsMaxDuration();
        }
        if (isRealTime) {
          maxCTime =
            getCompetitionStartDate() +
            (Math.min(+clock.now(), getCompetitionEndDate()) -
              getCompetitionStartDate());
        }
        currentTime = Math.min(+clock.now(), currentTime, maxCTime);
        const liveTime =
          +clock.now() - (fetchPositionInterval + 5 + sendInterval + 5) * 1e3;

        if (getCompetitionStartDate(true) !== null && currentTime > liveTime) {
          onSwitchToLive();
          return;
        }
      }
      if (ts - prevDisplayRefresh > 100) {
        const mustRefreshMeters = ts - prevMeterDisplayRefresh > 500;
        drawCompetitors(mustRefreshMeters);
        if (mustRefreshMeters) {
          prevMeterDisplayRefresh = ts;
        }
        prevDisplayRefresh = ts;
        prevShownTime = currentTime;
      }

      const isStillLive = isLiveEvent && eventEnd >= clock.now();
      const isBackLive = !isLiveEvent && eventEnd >= clock.now();
      if (!isStillLive) {
        u("#live_button")
          .off("click")
          .text(banana.i18n("archived-event"))
          .removeClass("btn-secondary", "d-none")
          .addClass("btn-info", "disabled");
        isLiveEvent = false;
      }
      if (isBackLive) {
        u("#live_button")
          .on("click", onSwitchToLive)
          .text(banana.i18n("return-live-mode"))
          .removeClass("d-none", "btn-info", "disabled")
          .addClass("btn-secondary");
        isLiveEvent = true;
      }
    }

    function whileReplay(ts) {
      renderReplay(ts);
      if (!isLive) {
        window.requestAnimationFrame(whileReplay);
      }
    }
    window.requestAnimationFrame(whileReplay);
  }

  this.getTailLength = function () {
    return tailLength;
  };

  function addRasterMapLayer(mapData, indexEventMap) {
    const bounds = ["topLeft", "topRight", "bottomRight", "bottomLeft"].map(
      function (corner) {
        const cornerCoords = mapData.coordinates[corner];
        return [cornerCoords.lat, cornerCoords.lon];
      }
    );
    let layer;
    if (mapData.wms) {
      layer = L.tileLayer.wms(
        `${window.local.wmsServiceUrl}?v=${mapData.hash}`,
        {
          layers: `${window.local.eventId}/${indexEventMap + 1}`,
          bounds: bounds,
          tileSize: 512,
          noWrap: true,
          maxNativeZoom: mapData.max_zoom,
        }
      );
    } else {
      layer = L.imageTransform(mapData.url, bounds);
      layer.options.bounds = bounds;
    }
    layer.data = mapData;
    return layer;
  }

  function onAppResize() {
    const doc = document.documentElement;

    doc.style.setProperty("--runner-scale", runnerIconScale);
    doc.style.setProperty("--app-height", `${window.innerHeight}px`);
    doc.style.setProperty(
      "--ctrl-height",
      `${document.getElementById("ctrl-wrapper").clientHeight}px`
    );
    doc.style.setProperty("--footer-size", "7px");
    doc.style.setProperty(
      "--navbar-size",
      document.fullscreenElement != null ? "0px" : "46px"
    );
    const width = window.innerWidth > 0 ? window.innerWidth : screen.width;
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
    const scrollTopDiv = u("#competitorList").first()?.scrollTop;
    const listDiv = u("<div/>");
    listDiv.addClass("mt-1");
    listDiv.attr({ id: "competitorList", "data-bs-theme": getCurrentTheme() });

    Object.values(competitorList).forEach(function (competitor, i) {
      if (
        searchText === null ||
        searchText === "" ||
        competitor.name.toLowerCase().search(searchText) != -1
      ) {
        listDiv.append(
          `<competitor-sidebar-el index="${i}" competitor-id="${competitor.id}"/>`
        );
      }
    });

    if (Object.keys(competitorList).length === 0) {
      const div = u(
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
      const mainDiv = u(
        '<div id="competitorSidebar" class="d-flex flex-column"/>'
      );
      const topDiv = u("<div/>");
      const searchBar = u("<form/>").addClass("row g-0 flex-nowrap");
      if (Object.keys(competitorList).length) {
        const toggleAllContent = u("<div/>")
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
        const toggleAllInput = u("<input/>")
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
      u("#competitorSidebar").append(listDiv);
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
      let minDist = Infinity;
      let minDistT = null;
      const route = competitorRoutes[competitor.id];

      if (route) {
        const length = route.getPositionsCount();
        for (let i = 0; i < length; i++) {
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
    const width = window.innerWidth > 0 ? window.innerWidth : screen.width;
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
    const perc =
      (e.pageX - document.getElementById("full_progress_bar").offsetLeft) /
      u("#full_progress_bar").size().width;
    onMoveProgressBar(perc);
  }

  function centerMap(e) {
    map.panTo(e.latlng);
  }

  function shareURL(e) {
    e.preventDefault();
    const shareData = {
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
    const touchLocation = e.targetTouches[0];
    const perc =
      (touchLocation.pageX -
        document.getElementById("full_progress_bar").offsetLeft) /
      u("#full_progress_bar").size().width;
    e.preventDefault();
    onMoveProgressBar(perc);
  }

  function fetchCompetitorRoutes(cb) {
    isCurrentlyFetchingRoutes = true;
    fetch(dataURL, {
      method: "GET",
      credentials: "include",
      mode: "cors",
    })
      .then((r) => r.json())
      .then(function (response) {
        if (!response || !response.competitors) {
          // Prevent fetching competitor data for 1 second
          setTimeout(function () {
            isCurrentlyFetchingRoutes = false;
          }, 1000);
          cb && cb();
          return;
        }
        const runnerPoints = [];

        response.competitors.forEach(function (competitor) {
          let route = null;
          if (competitor.encoded_data) {
            route = PositionArchive.fromEncoded(competitor.encoded_data);
            competitorRoutes[competitor.id] = route;
            if (zoomOnRunners) {
              const length = route.getPositionsCount();
              for (let i = 0; i < length; i++) {
                const pt = route.getByIndex(i);
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
      })
      .catch(function () {
        isCurrentlyFetchingRoutes = false;
      });
  }

  function zoomOnCompetitor(competitor) {
    if (!competitor.isShown || competitor.focusing) {
      return;
    }
    competitor.focusing = true;
    const route = competitorRoutes[competitor.id];
    if (!route) {
      competitor.focusing = false;
      return;
    }
    let timeT = currentTime;
    if (!isRealTime) {
      if (isCustomStart) {
        timeT += competitor.custom_offset - getCompetitionStartDate();
      } else {
        timeT += +new Date(competitor.start_time) - getCompetitionStartDate();
      }
    }
    const loc = route.getByTime(timeT);
    map.setView([loc.coords.latitude, loc.coords.longitude], map.getZoom(), {
      animate: true,
    });
    setTimeout(function () {
      competitor.focusing = false;
    }, 250);
  }

  function redrawCompetitorMarker(competitor, location, faded) {
    const coordinates = [location.coords.latitude, location.coords.longitude];
    const redraw =
      competitor.mapMarker && competitor.iconScale != runnerIconScale;
    if (redraw) {
      map.removeLayer(competitor.mapMarker);
      competitor.mapMarker = null;
    }
    if (!competitor.mapMarker) {
      const runnerIcon = getRunnerIcon(
        competitor.color,
        faded,
        competitor.highlighted,
        runnerIconScale
      );
      competitor.mapMarker = L.marker(coordinates, { icon: runnerIcon });
      competitor.mapMarker.addTo(map);
      competitor.iconScale = runnerIconScale;
    } else {
      competitor.mapMarker.setLatLng(coordinates);
    }
  }

  function redrawCompetitorNametag(competitor, location, faded) {
    const coordinates = [location.coords.latitude, location.coords.longitude];
    const pointX = map.latLngToContainerPoint(coordinates).x;
    const mapMiddleX = map.getSize().x / 2;
    const nametagOnRightSide = pointX > mapMiddleX;
    const nametagChangeSide =
      competitor.nameMarker &&
      (competitor.scale != runnerIconScale ||
        (competitor.isNameOnRight && !nametagOnRightSide) ||
        (!competitor.isNameOnRight && nametagOnRightSide));
    if (nametagChangeSide) {
      map.removeLayer(competitor.nameMarker);
      competitor.nameMarker = null;
    }
    if (!competitor.nameMarker) {
      competitor.isNameOnRight = nametagOnRightSide;
      const runnerIcon = getRunnerNameMarker(
        competitor.short_name,
        competitor.color,
        competitor.isColorDark,
        nametagOnRightSide,
        faded,
        competitor.highlighted,
        runnerIconScale
      );
      competitor.nameMarker = L.marker(coordinates, { icon: runnerIcon });
      competitor.nameMarker.addTo(map);
      competitor.scale = runnerIconScale;
    } else {
      competitor.nameMarker.setLatLng(coordinates);
    }
  }

  function redrawCompetitorTail(competitor, route, time) {
    let tail = null;
    let hasPointInTail = false;
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
      const tailLatLng = tail
        .getArray()
        .filter(function (pos) {
          return !isNaN(pos.coords.latitude);
        })
        .map(function (pos) {
          return [pos.coords.latitude, pos.coords.longitude];
        });

      const redraw = competitor.tail && competitor.tailScale != runnerIconScale;
      if (redraw) {
        map.removeLayer(competitor.tail);
        competitor.tail = null;
      }
      if (!competitor.tail) {
        competitor.tail = L.polyline(tailLatLng, {
          color: competitor.color,
          opacity: 0.75,
          weight: 5 * runnerIconScale,
          className: competitor.focused ? "icon-focused" : "",
        }).addTo(map);
        competitor.tailScale = runnerIconScale;
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
    let color = competitor.color;
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
    searchText = u(e.target).val().toLowerCase();
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
    const width = window.innerWidth > 0 ? window.innerWidth : screen.width;
    // show sidebar
    if (!sidebarShown || (u("#sidebar").hasClass("d-none") && width <= 576)) {
      showSidebar();
    }
    u("#permanent-sidebar .btn").removeClass("active");
    u("#options_show_button").addClass("active");
    optionDisplayed = true;
    searchText = null;
    const optionsSidebar = u("<div/>");
    optionsSidebar.css({
      "overflow-y": "auto",
      "overflow-x": "hidden",
    });
    optionsSidebar.attr({
      id: "optionsSidebar",
      "data-bs-theme": getCurrentTheme(),
    });

    {
      const tailLenWidget = u("<div/>").addClass("mb-2");

      const widgetTitle = u("<h4/>")
        .text(banana.i18n("tails"))
        .addClass("text-nowrap");

      const widgetContent = u("<div/>").addClass("form-group");

      const tailLenLabel = u("<label/>").text(banana.i18n("length-in-seconds"));

      const tailLenFormDiv = u("<div/>").addClass("row", "g-1");

      const hourInput = u("<input/>")
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

      const hourDiv = u("<div/>")
        .addClass("col-auto")
        .append(hourInput)
        .append("<span> : </span>");

      const minuteInput = u("<input/>")
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

      const minuteDiv = u("<div/>")
        .addClass("col-auto")
        .append(minuteInput)
        .append("<span> : </span>");

      const secondInput = u("<input/>")
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

      const secondDiv = u("<div/>").addClass("col-auto").append(secondInput);

      tailLenFormDiv.append(hourDiv).append(minuteDiv).append(secondDiv);

      tailLenFormDiv.find(".tailLengthControl").on("input", function (e) {
        const commonDiv = u(e.target).parent().parent();
        const hourInput = commonDiv.find('input[name="hours"]');
        const minInput = commonDiv.find('input[name="minutes"]');
        const secInput = commonDiv.find('input[name="seconds"]');
        const h = parseInt(hourInput.val() || 0);
        const m = parseInt(minInput.val() || 0);
        const s = parseInt(secInput.val() || 0);
        const v = 3600 * h + 60 * m + s;
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
      const sizeWidget = u("<div/>").addClass("mb-2");

      const widgetTitle = u("<h4/>")
        .text(banana.i18n("icons-size"))
        .addClass("text-nowrap");

      const label = u('<label for="icons-scale" class="fw-bold"/>').text(
        Math.round(runnerIconScale * 100) + "%"
      );

      const input = u(
        '<input type="range" class="form-range ps-1 pe-3" min="1" max="2" step="0.01" name="icons-scale">'
      );
      input.val(runnerIconScale);
      const onChange = (e) => {
        runnerIconScale = e.target.value;
        document.documentElement.style.setProperty(
          "--runner-scale",
          runnerIconScale
        );
        label.text(Math.round(runnerIconScale * 100) + "%");
      };
      input.on("change", onChange);
      input.on("input", onChange);

      const widgetContent = u("<div/>")
        .addClass("ms-1")
        .append(input)
        .append(label);

      sizeWidget.append(widgetTitle).append(widgetContent);

      optionsSidebar.append(sizeWidget);
    }

    {
      const ctrlWidget = u("<div/>").addClass("mb-2");

      const widgetTitle = u("<h4/>")
        .text(banana.i18n("map-controls"))
        .addClass("text-nowrap");

      const widgetContent = u("<div/>").addClass(
        "form-check",
        "form-switch",
        "d-inline-block",
        "ms-1"
      );

      const widgetInput = u("<input/>")
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
      const widgetLabel = u("<label/>")
        .addClass("form-check-label")
        .attr({ for: "toggleControlsSwitch" })
        .text(banana.i18n("show-map-controls"));

      widgetContent.append(widgetInput).append(widgetLabel);

      ctrlWidget.append(widgetTitle).append(widgetContent);

      optionsSidebar.append(ctrlWidget);
    }
    {
      const groupWidget = u("<div/>").addClass("mb-2");

      const widgetTitle = u("<h4/>")
        .text(banana.i18n("groupings"))
        .addClass("text-nowrap");

      const widgetContent = u("<div/>").addClass(
        "form-check",
        "form-switch",
        "d-inline-block",
        "ms-1"
      );

      const widgetInput = u("<input/>")
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
            for (const [key, cluster] of Object.entries(clusters)) {
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
      const widgetLabel = u("<label/>")
        .addClass("form-check-label")
        .attr({ for: "toggleClusterSwitch" })
        .text(banana.i18n("show-groupings"));

      widgetContent.append(widgetInput).append(widgetLabel);

      groupWidget.append(widgetTitle).append(widgetContent);

      optionsSidebar.append(groupWidget);
    }
    {
      const langWidget = u("<div/>").addClass("mb-2");

      const widgetTitle = u("<h4/>")
        .addClass("text-nowrap")
        .html(
          `<i class="fa-solid fa-language"></i> ${banana.i18n("language")}`
        );

      const langSelector = u("<select/>")
        .addClass("form-select")
        .attr({ ariaLabel: "Language" })
        .on("change", function (e) {
          window.localStorage.setItem("lang", e.target.value);
          window.location.search = `lang=${e.target.value}`;
        });

      Object.keys(supportedLanguages).forEach(function (lang) {
        const option = u("<option/>");
        option.attr({ value: lang });
        option.html(supportedLanguages[lang]);
        if (locale === lang) {
          option.attr({ selected: true });
        }
        langSelector.append(option);
      });

      langWidget.append(widgetTitle).append(langSelector);

      optionsSidebar.append(langWidget);
    }
    {
      const locWidget = u("<div/>").addClass("mb-2");

      const widgetTitle = u("<h4/>")
        .text(banana.i18n("location"))
        .addClass("text-nowrap");

      const widgetContent = u("<div/>").addClass(
        "form-check",
        "form-switch",
        "d-inline-block",
        "ms-1"
      );

      const widgetInput = u("<input/>")
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
      const widgetLabel = u("<label/>")
        .addClass("form-check-label")
        .attr({ for: "toggleLocationSwitch" })
        .text(banana.i18n("show-location"));

      widgetContent.append(widgetInput).append(widgetLabel);

      locWidget.append(widgetTitle).append(widgetContent);

      optionsSidebar.append(locWidget);
    }

    if (rasterMapLayer) {
      const toggleMapWidget = u("<div/>").addClass("mb-2");

      const widgetTitle = u("<h4/>")
        .text(banana.i18n("map"))
        .addClass("text-nowrap");

      const widgetContent = u("<div/>").addClass(
        "form-check",
        "form-switch",
        "d-inline-block",
        "ms-1"
      );

      const widgetInput = u("<input/>")
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
      const widgetLabel = u("<label/>")
        .addClass("form-check-label")
        .attr({ for: "toggleMapSwitch" })
        .text(banana.i18n("hide-map"));

      widgetContent.append(widgetInput).append(widgetLabel);

      toggleMapWidget.append(widgetTitle).append(widgetContent);

      optionsSidebar.append(toggleMapWidget);
    }

    {
      const bgMapWidget = u("<div/>").addClass("mb-2");

      const widgetTitle = u("<h4/>")
        .text(banana.i18n("background-map"))
        .addClass("text-nowrap");

      const mapSelector = u("<select/>")
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
            const layer = cloneLayer(backdropMaps[e.target.value]);
            layer.nickname = e.target.value;
            layer.setZIndex(-1);
            layer.addTo(map);
            bgLayer = layer;
          }
        });

      const blankOption = u("<option/>");
      blankOption.attr({ value: "blank" });
      blankOption.text("Blank");
      if (!bgLayer) {
        blankOption.attr({ selected: true });
      }
      mapSelector.append(blankOption);

      Object.entries(backgroundMapTitles).forEach(function (kv) {
        const option = u("<option/>");
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
      const qr = new QRious();
      qr.set({
        background: "#f5f5f5",
        foreground: "black",
        level: "L",
        value: shortcutURL,
        size: 138,
      });

      const qrWidget = u("<div/>").addClass("mb-2");

      const widgetTitle = u("<h4/>")
        .text(banana.i18n("qr-link"))
        .addClass("text-nowrap");

      qrWidget.append(widgetTitle);

      const widgetContent = u("<p/>").addClass("text-center");

      const qrImage = u("<img/>").attr({
        src: qr.toDataURL(),
        alt: "QR code for this event",
      });

      const qrText = u("<a/>")
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
    const coordinates = [location.coords.latitude, location.coords.longitude];
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
    let viewedTime = currentTime;
    if (isCustomStart) {
      viewedTime -= getCompetitorsMinCustomOffset();
    } else {
      viewedTime -= getCompetitionStartDate();
    }
    return viewedTime;
  }
  this.getRelativeTime = getRelativeTime;

  function getProgressBarText(
    currentTime,
    bg = false,
    date = false,
    relative = true
  ) {
    let result = "";
    if (bg && isLive) {
      return "";
    }
    let viewedTime = currentTime;
    if (!isRealTime || !relative) {
      if (currentTime === 0) {
        return "00:00:00";
      }
      if (relative) {
        if (isCustomStart) {
          viewedTime -= getCompetitorsMinCustomOffset();
        } else {
          viewedTime -= getCompetitionStartDate();
        }
      }
      const t = viewedTime / 1e3;

      function to2digits(x) {
        return ("0" + Math.floor(x)).slice(-2);
      }
      result += t > 3600 || bg ? Math.floor(t / 3600) + ":" : "";
      result += to2digits((t / 60) % 60) + ":" + to2digits(t % 60);
    } else {
      const t = Math.round(viewedTime / 1e3);
      if (t === 0) {
        return "00:00:00";
      }

      if (date) {
        result = dayjs(viewedTime).format("YYYY-MM-DD");
        if (bg) {
          result +=
            '<br><span class="time">' +
            dayjs(viewedTime).format("HH:mm:ss") +
            "</span>";
        } else {
          result += " " + dayjs(viewedTime).format("HH:mm:ss");
        }
      } else {
        result = dayjs(viewedTime).format("HH:mm:ss");
      }
    }
    return result;
  }
  this.getProgressBarText = getProgressBarText;

  function formatSpeed(s) {
    const min = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    if (min > 99) {
      return "--'--\"/km";
    }
    return min + "'" + ("0" + sec).slice(-2) + '"/km';
  }

  function checkVisible(elem) {
    if (!sidebarShown) {
      return false;
    }
    const bcr = elem.getBoundingClientRect();
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
      const playButton =
        '<i class="fa-solid fa-play fa-fw"></i> x' + playbackRate;
      if (u("#play_pause_button").html() != playButton) {
        u("#play_pause_button").html(playButton);
      }
    } else {
      const pauseButton =
        '<i class="fa-solid fa-pause fa-fw"></i> x' + playbackRate;
      if (u("#play_pause_button").html() != pauseButton) {
        u("#play_pause_button").html(pauseButton);
      }
    }
    onAppResize();
    // progress bar
    let perc = 0;
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

    startLineCrosses = [];
    splitTimes = [];

    Object.values(competitorList).forEach(function (competitor) {
      if (!competitor.isShown) {
        return;
      }
      const route = competitorRoutes[competitor.id];
      if (route !== undefined) {
        let viewedTime = currentTime;
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
        const loc = route.getByTime(viewedTime);
        const hasRecentPoints = route.hasPointInInterval(
          viewedTime - (sendInterval * 4 + fetchPositionInterval) * 1e3, //kayak
          viewedTime
        );
        if (competitor.focused) {
          keepFocusOnCompetitor(competitor, loc);
        }

        const beforeFirstPoint = route.getByIndex(0).timestamp > viewedTime;
        if (beforeFirstPoint) {
          clearCompetitorLayers(competitor);
        }

        const isIdle =
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
          const hasPointInTail = route.hasPointInInterval(
            viewedTime - 30 * 1e3,
            viewedTime
          );
          if (!hasPointInTail) {
            competitor.speedometerValue = "--'--\"/km";
            competitor.speedometer.textContent = competitor.speedometerValue;
          } else {
            if (checkVisible(competitor.speedometer)) {
              let distance = 0;
              let prevPos = null;
              const tail30s = route.extractInterval(
                viewedTime - 30 * 1e3,
                viewedTime
              );
              tail30s.getArray().forEach(function (pos) {
                if (prevPos && !isNaN(pos.coords.latitude)) {
                  distance += pos.distance(prevPos);
                }
                prevPos = pos;
              });
              const speed = (30 / distance) * 1000;
              competitor.speedometerValue = formatSpeed(speed);
              competitor.speedometer.textContent = competitor.speedometerValue;
            }
          }
          if (checkVisible(competitor.odometer)) {
            const totalDistance = route.distanceUntil(viewedTime);
            competitor.odometerValue = (totalDistance / 1000).toFixed(1) + "km";
            competitor.odometer.textContent = competitor.odometerValue;
          }

          // Splittimes
          if (
            refreshMeters &&
            removeSplitLinesContextMenuItem.find(function (a) {
              return !!a;
            })
          ) {
            const allPoints = route.getArray();
            let crossCount = 0;
            let startPointIdx = null;
            for (let i = 1; i < allPoints.length; i++) {
              const prevPoint = allPoints[i - 1];
              const currPoint = allPoints[i];
              if (
                !isLive &&
                !isRealTime &&
                isCustomStart &&
                competitor.custom_offset &&
                currPoint.timestamp < competitor.custom_offset
              ) {
                continue;
              }
              if (viewedTime < currPoint.timestamp) {
                break;
              }
              if (rankingFromSplit != null) {
                const prevXY = map.project(
                  L.latLng([
                    prevPoint.coords.latitude,
                    prevPoint.coords.longitude,
                  ]),
                  intersectionCheckZoom
                );
                const currXY = map.project(
                  L.latLng([
                    currPoint.coords.latitude,
                    currPoint.coords.longitude,
                  ]),
                  intersectionCheckZoom
                );
                const lineAXY = map.project(
                  splitLinesPoints[rankingFromSplit][0],
                  intersectionCheckZoom
                );
                const lineBXY = map.project(
                  splitLinesPoints[rankingFromSplit][1],
                  intersectionCheckZoom
                );
                if (
                  L.LineUtil.segmentsIntersect(prevXY, currXY, lineAXY, lineBXY)
                ) {
                  crossCount++;
                  if (crossCount == rankingFromLap) {
                    let competitorTime =
                      prevPoint.timestamp +
                      intersectRatio(prevXY, currXY, lineAXY, lineBXY) *
                        (currPoint.timestamp - prevPoint.timestamp);
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

                    if (getRelativeTime(competitorTime) < 0) {
                      crossCount--;
                      continue;
                    }

                    startLineCrosses.push({
                      competitor: competitor,
                      time: competitorTime,
                    });
                    startPointIdx =
                      i + (rankingFromSplit != rankingToSplit ? 0 : 1);
                    break;
                  }
                }
              } else {
                startPointIdx = i;
                break;
              }
            }
            crossCount = 0;
            if (startPointIdx != null) {
              for (let i = startPointIdx; i < allPoints.length; i++) {
                const prevPoint = allPoints[i - 1];
                const currPoint = allPoints[i];
                if (viewedTime < currPoint.timestamp) {
                  break;
                }
                const prevXY = map.project(
                  L.latLng([
                    prevPoint.coords.latitude,
                    prevPoint.coords.longitude,
                  ]),
                  intersectionCheckZoom
                );
                const currXY = map.project(
                  L.latLng([
                    currPoint.coords.latitude,
                    currPoint.coords.longitude,
                  ]),
                  intersectionCheckZoom
                );
                const lineAXY = map.project(
                  splitLinesPoints[rankingToSplit][0],
                  intersectionCheckZoom
                );
                const lineBXY = map.project(
                  splitLinesPoints[rankingToSplit][1],
                  intersectionCheckZoom
                );
                if (
                  L.LineUtil.segmentsIntersect(prevXY, currXY, lineAXY, lineBXY)
                ) {
                  crossCount++;
                  if (crossCount == rankingToLap) {
                    let competitorTime =
                      prevPoint.timestamp +
                      intersectRatio(prevXY, currXY, lineAXY, lineBXY) *
                        (currPoint.timestamp - prevPoint.timestamp);
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

                    if (getRelativeTime(competitorTime) < 0) {
                      crossCount--;
                      continue;
                    }

                    if (rankingFromSplit != null) {
                      competitorTime -= startLineCrosses.find(function (c) {
                        return c.competitor.id === competitor.id;
                      }).time;
                      if (competitorTime < 0) {
                        crossCount--;
                        continue;
                      }
                    }

                    splitTimes.push({
                      competitor: competitor,
                      time: competitorTime,
                    });
                    break;
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
      const competitorsWithMarker = [];
      const competitorsLocations = [];
      Object.values(competitorList).forEach(function (competitor) {
        if (competitor.mapMarker) {
          competitorsWithMarker.push(competitor);
          const latLon = competitor.mapMarker.getLatLng();
          competitorsLocations.push({
            location: {
              accuracy: 0,
              latitude: latLon.lat,
              longitude: latLon.lng,
            },
          });
        }
      });
      const dbscanner = jDBSCAN()
        .eps(0.015)
        .minPts(1)
        .distance("HAVERSINE")
        .data(competitorsLocations);
      const competitorClusters = dbscanner();
      const clustersCenter = dbscanner.getClusters();

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
          const cluster = clusters[d] || {};
          const clusterCenter = clustersCenter[d - 1];
          if (!cluster.color) {
            cluster.color = getColor(d - 1);
            cluster.isColorDark = getContrastYIQ(cluster.color);
          }
          clustersCenter[d - 1].color = cluster.color;
          const competitorInCluster = competitorsWithMarker[i];
          ["mapMarker", "nameMarker"].forEach(function (layerName) {
            if (competitorInCluster[layerName]) {
              map.removeLayer(competitorInCluster[layerName]);
            }
            competitorInCluster[layerName] = null;
          });
          cluster.name = `${banana.i18n("group")} ${alphabetizeNumber(d - 1)}`;
          cluster.short_name = cluster.name;
          const clusterLoc = { coords: clusterCenter.location };
          redrawCompetitorMarker(cluster, clusterLoc, false);
          redrawCompetitorNametag(cluster, clusterLoc, false);
          clusters[d] = cluster;
        }
      });

      groupControl.setValues(competitorsWithMarker, clustersCenter);
    }
    if (
      removeSplitLinesContextMenuItem.find(function (a) {
        return !!a;
      }) &&
      refreshMeters
    ) {
      rankControl.setValues(splitTimes);
    }
  }
}

(function () {
  if (!navigator.canShare) {
    document.getElementById("share_buttons").remove();
  }

  (async () => {
    try {
      await navigator.wakeLock.request("screen");
    } catch (err) {
      console.log("Wake Lock Screen failed");
    }
  })();
  document.addEventListener("visibilitychange", async () => {
    if (document.visibilityState === "visible") {
      try {
        await navigator.wakeLock.request("screen");
      } catch (err) {
        console.log("Wake Lock Screen failed");
      }
    }
  });

  const queryString = window.location.search;
  const urlParams = new URLSearchParams(queryString);

  const urlLanguage = getLangIfSupported(urlParams.get("lang"));
  const storedLanguage = getLangIfSupported(
    window.localStorage.getItem("lang")
  );
  const browserLanguage = getLangIfSupported(navigator.language.slice(0, 2));
  locale = urlLanguage || storedLanguage || browserLanguage || "en";
  document.documentElement.setAttribute("lang", locale);
  dayjs.locale(locale);
  banana = new Banana();
  updateText().then(function () {
    u("#event-start-date-text").text(banana.i18n("event-start-date-text"));
    u("#heads-up-text").text(banana.i18n("heads-up-text"));
    u("#export-text").text(banana.i18n("export"));
    u("#event-start-list-link").text(banana.i18n("start-list"));
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
        const path = e.composedPath();
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

    const elem = document.getElementById("main-div");
    if (
      !elem.requestFullscreen &&
      !elem.webkitRequestFullscreen &&
      !elem.msRequestFullscreen
    ) {
      document.getElementById("fullscreenSwitch").remove();
    }
    myEvent = new RCEvent(window.local.eventUrl, window.local.serverClockUrl);
  });
})();
