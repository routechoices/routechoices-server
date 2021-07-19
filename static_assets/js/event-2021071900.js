L.Control.Ranking = L.Control.extend({
  
  onAdd: function(map) {
      var back = L.DomUtil.create('div', 'leaflet-bar leaflet-control leaflet-control-ranking');
      back.style.width = '205px';
      back.style.background = 'white'
      back.style['max-height'] = '195px'
      back.style['overflow-y'] = 'scroll'
      back.style['overflow-x'] = 'hidden'
      return back;
  },

  setValues(ranking) {
    var el = $('.leaflet-control-ranking')
    var out = ''
    ranking.sort(function(a, b) {return getRelativeTime(a.time) - getRelativeTime(b.time)})
    ranking.forEach(function (c, i) {
      out += '<div style="clear:both;white-space:nowrap;width:200px;height:1em"><span style="float:left;display:inline-block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;width:135px;">' + (i+1) + ' <span style="color: '+ c.competitor.color +'">⬤</span> ' + $('<span/>').text(c.competitor.name).html() + '</span><span style="float:right;display:inline-block;white-space:nowrap;overflow:hidden;width:55px;font-feature-settings:tnum;font-variant-numeric:tabular-nums lining-nums;margin-right:10px">' + getProgressBarText(c.time) + '</span></div>'
    })
    if (el.html() !== out){
      el.html(out)
    }
  },

  onRemove: function(map) {
    $('.leaflet-control-ranking').remove()
  }
});

L.control.ranking = function(opts) {
  return new L.Control.Ranking(opts);
}

Array.prototype.findIndex = Array.prototype.findIndex || function(callback) {
    if (this === null) {
      throw new TypeError('Array.prototype.findIndex called on null or undefined');
    } else if (typeof callback !== 'function') {
      throw new TypeError('callback must be a function');
    }
    var list = Object(this);
    // Makes sures is always has an positive integer as length.
    var length = list.length >>> 0;
    var thisArg = arguments[1];
    for (var i = 0; i < length; i++) {
      if ( callback.call(thisArg, list[i], i, list) ) {
        return i;
      }
    }
    return -1;
  };
  var COLORS = [
    '#e6194B',
    '#3cb44b',
    '#4363d8',
    '#f58231',
    '#911eb4',
    '#42d4f4',
    '#f032e6',
    '#bfef45',
    '#469990',
    '#9A6324',
    '#800000',
    '#aaffc3',
    '#808000',
    '#000075',
    '#ffe119',
    '#a9a9a9',
    '#000000'
  ]
  var getColor = function(i) {
    return COLORS[i % COLORS.length]
  }
  function getContrastYIQ(hexcolor){
    hexcolor = hexcolor.replace("#", "");
    var r = parseInt(hexcolor.substr(0,2),16);
    var g = parseInt(hexcolor.substr(2,2),16);
    var b = parseInt(hexcolor.substr(4,2),16);
    var yiq = ((r*299)+(g*587)+(b*114))/1000;
    return (yiq <= 168) ? 'dark' : 'light';
  }
var map = null;
var isLiveMode = false;
var liveUrl = null;
var isLiveEvent = false;
var isRealTime = true;
var isCustomStart = false;
var openStreetMap = null;
var competitorList = [];
var competitorRoutes = {};
var routesLastFetched = -Infinity;
var noticeLastFetched = -Infinity;
var timeOffsetSec = 0;
var playbackRate = 1;
var playbackPaused = true;
var prevDisplayRefresh = 0;
var tailLength = 60;
var isCurrentlyFetchingRoutes = false;
var isCurrentlyFetchingNotice = false;
var currentTime = 0;
var lastDataTs = 0;
var lastNbPoints = 0;
var optionDisplayed = false;
var mapDetailsUrl = null;
var mapHash = '';
var mapUrl = null;
var rasterMap = null;
var searchText = null;
var noticeUrl = null;
var prevNotice = new Date(0);
var resetMassStartContextMenuItem = null;
var setMassStartContextMenuItem = null;
var setFinishLineContextMenuItem = null;
var removeFinishLineContextMenuItem = null;

var qrUrl = null
var finishLineCrosses = [];
var finishLinePoints = [];
var finishLinePoly = null;
var rankControl = null;

function drawFinishLine (e) {
  finishLinePoints = [];
  if(finishLinePoly){
    map.removeLayer(finishLinePoly);
    map.removeControl(rankControl);
    finishLinePoly = null;
  };
	finishLinePoints.push(e.latlng);
  map.on('click', drawFinishLineEnd);
}

function removeFinishLine() {
  if(finishLinePoly){
    map.removeLayer(finishLinePoly);
    map.removeControl(rankControl);
    finishLinePoly = null;
    map.contextmenu.removeItem(removeFinishLineContextMenuItem);
    removeFinishLineContextMenuItem = null;
    setFinishLineContextMenuItem = map.contextmenu.insertItem({
      text: 'Draw finish line',
      callback: drawFinishLine
    }, 1);
  };
}

function drawFinishLineEnd(e) {
  finishLinePoints.push(e.latlng);
  finishLinePoly = L.polyline(finishLinePoints, {color: 'purple'});
  map.off('click', drawFinishLineEnd);
  rankControl = L.control.ranking({ position: 'topright' })
  map.addControl(rankControl);
  map.addLayer(finishLinePoly);
  map.contextmenu.removeItem(setFinishLineContextMenuItem);
  setFinishLineContextMenuItem = null;
  removeFinishLineContextMenuItem = map.contextmenu.insertItem({
      text: 'Remove finish line',
      callback: removeFinishLine
  }, 1);
}

var onStart = function(){
  if(isLiveEvent){
    selectLiveMode();
  } else {
    $("#live_button").hide();
    selectReplayMode();
  }
  fetchCompetitorRoutes();
};

var selectLiveMode = function(e){
  if(e !== undefined){
    e.preventDefault();
  }
  if(isLiveMode){
    return;
  }
  if (setMassStartContextMenuItem) {
     map.contextmenu.removeItem(setMassStartContextMenuItem);
     setMassStartContextMenuItem = null;
  }
  if (resetMassStartContextMenuItem) {
     map.contextmenu.removeItem(resetMassStartContextMenuItem);
     resetMassStartContextMenuItem = null;
  }
  $("#live_button").addClass('active');
  $("#replay_button").removeClass('active');
  $("#replay_mode_buttons").hide();
  $("#replay_control_buttons").hide();
  timeOffsetSec = -30;
  isLiveMode=true;

  (function whileLive(){
    if (+clock.now()-routesLastFetched > -timeOffsetSec * 1e3 && !isCurrentlyFetchingRoutes) {
      fetchCompetitorRoutes();
      fetchMapDetails();
    }
    if(((+clock.now() - noticeLastFetched) > (30 * 1e3)) && !isCurrentlyFetchingNotice){
      fetchNotice(); 
    }
    currentTime = +clock.now() - 5 * 1e3 + timeOffsetSec * 1e3;
    drawCompetitors();
    if (isLiveMode) {
      setTimeout(whileLive, 101);
    }
  })()
}

var selectReplayMode = function(e){
  if(e !== undefined){
    e.preventDefault();
  }
  if(!isLiveMode && $("#replay_button").hasClass('active')){
    return;
  }
  $("#live_button").removeClass('active');
  $("#replay_button").addClass('active');
  $("#replay_mode_buttons").show();
  $("#replay_control_buttons").show();
  if (!setMassStartContextMenuItem) {
    setMassStartContextMenuItem = map.contextmenu.insertItem({
      text: 'Mass Start from here',
      callback: onPressCustomMassStart
    }, 2);
  }
  isLiveMode = false;
  prevShownTime = getCompetitionStartDate();
  playbackPaused = true;
  playbackRate = 1;
  prevDisplayRefresh = +clock.now();
  (function whileReplay(){
    if(isLiveEvent && + clock.now() - routesLastFetched > -timeOffsetSec * 1e3 && !isCurrentlyFetchingRoutes){
      fetchCompetitorRoutes(); 
    }
    if(((+clock.now() - noticeLastFetched) > (30 * 1e3)) && !isCurrentlyFetchingNotice){
      fetchNotice(); 
    }
    var actualPlaybackRate = playbackPaused ? 0 : playbackRate;
    currentTime = Math.max(getCompetitionStartDate(), prevShownTime + (+clock.now() - prevDisplayRefresh) * actualPlaybackRate);
    currentTime = Math.min(+clock.now(), currentTime, getCompetitionEndDate());
    drawCompetitors();
    prevShownTime = currentTime;
    prevDisplayRefresh = +clock.now();
    if(!isLiveMode){
      setTimeout(whileReplay, 101);
    }
  })()
}

var fetchCompetitorRoutes = function(url){
  isCurrentlyFetchingRoutes = true;
  url = url || liveUrl;
  var data = {lastDataTs: Math.round(lastDataTs/15)*15};
  $.ajax({
    url: url,
    data: data
  }).done(function(response){
    response.competitors.forEach(function(competitor){
      if(competitor.encoded_data) {
        var route = PositionArchive.fromTks(competitor.encoded_data);
        competitorRoutes[competitor.id] = route;
      }
    });
    updateCompetitorList(response.competitors);
    displayCompetitorList();
    routesLastFetched = +clock.now();
    lastDataTs = response.timestamp;
    isCurrentlyFetchingRoutes = false;
    $('#eventLoadingModal').remove()
  }).fail(function(){
    isCurrentlyFetchingRoutes = false;
  });
};
var fetchMapDetails = function() {
  $.ajax({
    url: mapDetailsUrl
  }).done(function(response){
    if (mapHash != response.hash) {
      mapHash = response.hash;
      if (mapHash != '') {
        var lastMod = + new Date(response.last_mod);
        var stemp = response.corners_coordinates.split(',');
        removeRasterMap();
        addRasterMap([1*stemp[0],1*stemp[1]],[1*stemp[2],1*stemp[3]],[1*stemp[4],1*stemp[5]],[1*stemp[6],1*stemp[7]], mapUrl + '?t=' + lastMod);
      } else {
        removeRasterMap();
      }
    }
  })
};
var fetchNotice = function() {
  isCurrentlyFetchingNotice = true;
  $.ajax({
    url: noticeUrl
  }).done(function(response){
    noticeLastFetched = +clock.now();
    isCurrentlyFetchingNotice = false;
    if (response.updated && response.text && new Date(response.updated) > prevNotice) {
      prevNotice = new Date(response.updated);
      $('#alert-text').text(response.text);
      $('.page-alerts').show();
      $('.page-alert').slideDown();
    } else {
      isCurrentlyFetchingNotice = false;
    }
  })
}
var updateCompetitorList = function(newList) {
    newList.forEach(updateCompetitor)
}

var setCustomStart = function (latlng) {
  competitorList.forEach(function(c){
    var minDist = Infinity;
    var minDistT = null;
    var route = competitorRoutes[c.id];
    if(route) {
      var length = route.getPositionsCount();
      for (var i = 0; i < length; i++) {
        dist = route.getByIndex(i).distance({coords: {latitude: latlng.lat, longitude: latlng.lng}});
        if (dist < minDist) {
          minDist = dist;
          minDistT = route.getByIndex(i).timestamp;
        }
      }
      c.custom_offset = minDistT;
    }
  })
}

var updateCompetitor = function(newData) {
    var idx = competitorList.findIndex(function(c){return c.id == newData.id})
    if (idx != -1) {
        var c = competitorList[idx];
        Object.keys(newData).forEach(function(k){
            c[k] = newData[k];
        })
        competitorList[idx] = c;
    } else {
        competitorList.push(newData);
    }
}

var displayCompetitorList = function(){
    if (optionDisplayed){
      return;
    }
    var listDiv = $('<ul id="listCompetitor"/>');
    listDiv.addClass('media-list');
    competitorList.forEach(function(competitor, ii){
      competitor.color = competitor.color || getColor(ii);
      competitor.isShown = (typeof competitor.isShown === "undefined") ? true : competitor.isShown;
      var div = $('<li/>');
      div.addClass('media').html('\
        <div class="media-left"><i class="media-object fa fa-circle fa-3x" style="color:' + competitor.color + '"></i></div>\
        <div class="media-body"><b>'+ $('<span/>').text(competitor.name).html() +'</b><br/>\
          <div class="btn-group btn-group-xs" role="group">\
            <button type="button" class="toggle_competitor_btn btn btn-default"><i class="fa fa-toggle-' + (competitor.isShown ? 'on' : 'off') + '"></i></button>\
            <button type="button" class="center_competitor_btn btn btn-default"><i class="fa fa-map-marker"></i></button>\
          </div>\
          <span><small class="speedometer"></small></span>\
        </div>')
      $(div).find('.toggle_competitor_btn').on('click', function(e){
        e.preventDefault();
        var icon = $(this).find('i');
        if(icon.hasClass('fa-toggle-on')){
          icon.removeClass('fa-toggle-on').addClass('fa-toggle-off');
          competitor.isShown = false;
          if(competitor.mapMarker) {
            map.removeLayer(competitor.mapMarker);
          }
          if(competitor.nameMarker) {
            map.removeLayer(competitor.nameMarker);
          }
          if(competitor.tail) {
            map.removeLayer(competitor.tail);
          }
          competitor.mapMarker = null;
          competitor.nameMarker = null;
          competitor.tail = null;
          updateCompetitor(competitor);
        }else{
          icon.removeClass('fa-toggle-off').addClass('fa-toggle-on');
          competitor.isShown = true;
          updateCompetitor(competitor);
        }
      });
      $(div).find('.center_competitor_btn').on('click', function(){
        zoomOnCompetitor(competitor);
      });
      if(searchText === null || searchText === '' || competitor.name.toLowerCase().search(searchText) != -1) {
        listDiv.append(div);
      }
      competitor.div = div;
      competitor.speedometer = div.find('.speedometer');
    });
    if(searchText === null) {
      var mainDiv = $('<div id="competitorSidebar"/>');
      mainDiv.append(
        $('<div style="text-align:right; margin: -10px 0px 10px 0px;"/>').append(
          $('<button class="btn btn-default btn-xs"/>').html('<i class="fa fa-cog"></i>').on('click', displayOptions)
        )
      );
      if(competitorList.length > 10) {
        mainDiv.append(
          $('<input class="form-control" placeholder="Search Competitors" val="'+searchText+'"/>').on('keyup', filterCompetitorList)
        );
      }
      mainDiv.append(listDiv);
      $('#sidebar').html('');
      $('#sidebar').append(mainDiv);
    } else {
      $('#listCompetitor').remove();
      var mainDiv = $('#competitorSidebar');
      mainDiv.append(listDiv);
    }
}

var filterCompetitorList = function(e) {
    var inputVal = $(e.target).val();
    searchText = inputVal.toLowerCase();
    displayCompetitorList();
}

var displayOptions = function() {
    optionDisplayed = true;
    searchText = null;
    var mainDiv = $('<div/>');
    mainDiv.append(
      $('<div style="text-align:right; margin: -10px 0px 10px 0px;"/>').append(
        $('<button class="btn btn-default btn-xs"/>')
        .html('<i class="fa fa-times"></i>')
        .on('click', function(){
          optionDisplayed = false;
          displayCompetitorList();
        })
      )
    );
    var qr = qrcode(0, 'L');
    qr.addData(qrUrl)
    qr.make()
    var qrDataUrl = qr.createDataURL(4);
    mainDiv.append(
      $('<div"/>').html(
        '<h4>Competitors</h4>' +
        '<div>' +
        '<button id="hideAllCompetitorBtn" class="btn btn-default"><i class="fa fa-eye-slash"></i> Hide All</button>' +
        '<button id="showAllCompetitorBtn" class="btn btn-default"><i class="fa fa-eye"></i> Show All</button>' +
        '</div>' +
        '<h4>Tails</h4>' +
        '<div class="form-group">' +
        '<label for="tailLengthInput">Length in seconds</label>' +
        '<input type="number" min="0" class="form-control" id="tailLengthInput" value="'+ tailLength +'"/>' +
        (qrUrl ? ('<h4>QR Link</h4><p style="text-align:center"><img style="margin-bottom:15px" src="' + qrDataUrl + '" alt="qr"><br/><a  href="'+ qrUrl +'">'+qrUrl+'</a></p>') : '') +
        '</div>'
      )
    );
    $(mainDiv).find('#tailLengthInput').on('input', function(e){
      var v = parseInt(e.target.value);
      if (isNaN(v)) {
        v = 0;
      }
      tailLength = Math.max(0, v);
    });
    $(mainDiv).find('#hideAllCompetitorBtn').on('click', function(){
      competitorList.forEach(function(competitor){
        competitor.isShown = false;
        if(competitor.mapMarker) {
          map.removeLayer(competitor.mapMarker);
        }
        if(competitor.nameMarker) {
          map.removeLayer(competitor.nameMarker);
        }
        if(competitor.tail) {
          map.removeLayer(competitor.tail);
        }
        competitor.mapMarker = null;
        competitor.nameMarker = null;
        competitor.tail = null;
        updateCompetitor(competitor);
      })
    });
    $(mainDiv).find('#showAllCompetitorBtn').on('click', function(){
      competitorList.forEach(function(competitor){
        competitor.isShown = true;
        updateCompetitor(competitor);
      })
    });

    $('#sidebar').html('');
    $('#sidebar').append(mainDiv);
}

var getCompetitionStartDate = function() {
    var res = +clock.now();
    competitorList.forEach(function(c){
        var route = competitorRoutes[c.id];
        if(route) {
            res = res>route.getByIndex(0).timestamp?route.getByIndex(0).timestamp: res;
        }
    })
    return res
}
var getCompetitionEndDate = function() {
    var res = new Date(0);
    competitorList.forEach(function(c){
        var route = competitorRoutes[c.id];
        if(route) {
            var idx = route.getPositionsCount()-1;
            res = res<route.getByIndex(idx).timestamp?route.getByIndex(idx).timestamp: res;
        }
    })
    return res
}
var getCompetitorsMaxDuration = function(customOffset) {
    if(customOffset === undefined) {
      customOffset = false;
    }
    var res = 0;
    competitorList.forEach(function(c){
        var route = competitorRoutes[c.id];
        if(route) {
            var idx = route.getPositionsCount()-1;

            var dur = route.getByIndex(idx).timestamp - ((customOffset ? +new Date(c.custom_offset) : +new Date(c.start_time)) || getCompetitionStartDate());
            res = res < dur ? dur : res;
        }
    })
    return res
}
var getCompetitorsMinCustomOffset = function() {
    var res = 0;
    competitorList.forEach(function(c){
        var route = competitorRoutes[c.id];
        if(route) {
          var off = (c.custom_offset - c.start_time) || 0;
          res = res < off ? off : res;
        }
    })
    return res
}

var zoomOnCompetitor = function(compr){
  var route = competitorRoutes[compr.id];
  if(!route) return
  var timeT = currentTime;
  if(!isRealTime){
    if (isCustomStart) {
      timeT += +new Date(compr.custom_offset) - getCompetitionStartDate();
    } else {
      timeT += +new Date(compr.start_time) - getCompetitionStartDate();
    }
  }
  var loc = route.getByTime(timeT);
  map.setView([loc.coords.latitude, loc.coords.longitude]);
}
var getRelativeTime = function(currentTime) {
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
var getProgressBarText = function(currentTime){
    var result = '';
    var viewedTime = currentTime;
    if (!isRealTime) {
        if (isCustomStart) {
          viewedTime -= getCompetitorsMinCustomOffset() + getCompetitionStartDate();
        } else {
          viewedTime -= getCompetitionStartDate();
        }
        var t = viewedTime / 1e3;
        to2digits = function(x){return ('0'+Math.floor(x)).slice(-2);},
        result += t > 3600 ? Math.floor(t/3600) + ':': '';
        result += to2digits((t / 60) % 60) + ':' + to2digits(t % 60);
    } else {
        result = luxon.DateTime.fromMillis(viewedTime).toFormat('TT');
    }
    return result;
}
var drawCompetitors = function(){
  // play/pause button
  if(playbackPaused){
    var html = '<i class="fa fa-play"></i> x'+playbackRate;
    if($('#play_pause_button').html() != html){
      $('#play_pause_button').html(html);
    }
  } else {
    var html = '<i class="fa fa-pause"></i> x'+playbackRate;
    if($('#play_pause_button').html() != html){
      $('#play_pause_button').html(html);
    }
  }
  // progress bar
  var perc = 0;
  if (isRealTime) {
    perc = isLiveMode ? 100 : (currentTime-getCompetitionStartDate())/(Math.min(+clock.now(), getCompetitionEndDate())-getCompetitionStartDate()) * 100
  } else {
    if (isCustomStart) {
      perc = (currentTime-(getCompetitionStartDate()+getCompetitorsMinCustomOffset())) / getCompetitorsMaxDuration(true) * 100;
    } else {
      perc = (currentTime-getCompetitionStartDate()) / getCompetitorsMaxDuration() * 100;
    }
  }
  $('#progress_bar').css('width', perc+'%').attr('aria-valuenow', perc);
  $('#progress_bar_text').html(getProgressBarText(currentTime));
  var oldFinishCrosses = finishLineCrosses.slice();
  finishLineCrosses = [];
  competitorList.forEach(function(competitor){
    if(!competitor.isShown){
      return;
    }
    var route = competitorRoutes[competitor.id];
    if(route !== undefined){
      var viewedTime = currentTime;
      if(!isLiveMode && !isRealTime && !isCustomStart && competitor.start_time){
        viewedTime += Math.max(0, new Date(competitor.start_time) - getCompetitionStartDate());
      }
      if(!isLiveMode && !isRealTime && isCustomStart && competitor.custom_offset){
        viewedTime += Math.max(0, new Date(competitor.custom_offset) - getCompetitionStartDate());
      }
      if(finishLinePoly) {
        var allPoints = route.getArray();
        var oldCrossing = oldFinishCrosses.find(function(el){return el.competitor.id === competitor.id});
        var useOldCrossing = false
        if (oldCrossing) {
          var oldTs = allPoints[oldCrossing.idx].timestamp;
          if (viewedTime >= oldTs) {
            if (L.LineUtil.segmentsIntersect(
              map.project(finishLinePoints[0], 16),
              map.project(finishLinePoints[1], 16),
              map.project(L.latLng([allPoints[oldCrossing.idx].coords.latitude, allPoints[oldCrossing.idx].coords.longitude]), 16),
              map.project(L.latLng([allPoints[oldCrossing.idx-1].coords.latitude, allPoints[oldCrossing.idx-1].coords.longitude]), 16)
            )
            ) {
              var competitorTime = allPoints[oldCrossing.idx].timestamp;
              if(!isLiveMode && !isRealTime && !isCustomStart && competitor.start_time){
                competitorTime -= Math.max(0, new Date(competitor.start_time) - getCompetitionStartDate());
              }
              if(!isLiveMode && !isRealTime && isCustomStart && competitor.custom_offset){
                competitorTime -= Math.max(0, new Date(competitor.custom_offset) - getCompetitionStartDate());
              }
              if (getRelativeTime(competitorTime) > 0) {
                finishLineCrosses.push({
                  competitor, 
                  time: competitorTime,
                  idx: oldCrossing.idx
                });
                useOldCrossing = true;
              }
            }
          }
        }
        if(!useOldCrossing) {
          for (var i=1; i < allPoints.length; i++) {
            var tPoint = allPoints[i];
            if (viewedTime < tPoint.timestamp) {
              break
            }
            if (L.LineUtil.segmentsIntersect(
                map.project(finishLinePoints[0], 16),
                map.project(finishLinePoints[1], 16),
                map.project(L.latLng([tPoint.coords.latitude, tPoint.coords.longitude]), 16),
                map.project(L.latLng([allPoints[i-1].coords.latitude, allPoints[i-1].coords.longitude]), 16)
              )
            ) {
              var competitorTime = tPoint.timestamp;
              if(!isLiveMode && !isRealTime && !isCustomStart && competitor.start_time){
                competitorTime -= Math.max(0, new Date(competitor.start_time) - getCompetitionStartDate());
              }
              if(!isLiveMode && !isRealTime && isCustomStart && competitor.custom_offset){
                competitorTime -= Math.max(0, new Date(competitor.custom_offset) - getCompetitionStartDate());
              }
              if (getRelativeTime(competitorTime) > 0) {
                finishLineCrosses.push({
                  competitor, 
                  time: competitorTime,
                  idx: i
                });
                break;
              }
            }
          }
        }
      }
      var hasPointLast30sec = route.hasPointInInterval(viewedTime - 30 * 1e3, viewedTime);
      if(!hasPointLast30sec){
          if(competitor.mapMarker) {
            map.removeLayer(competitor.mapMarker);
          }
          if(competitor.nameMarker) {
            map.removeLayer(competitor.nameMarker);
          }
          competitor.mapMarker = null;
          competitor.nameMarker = null;
      }
      var loc = route.getByTime(viewedTime);
      if(loc && !isNaN(loc.coords.latitude) && hasPointLast30sec){
        if(competitor.mapMarker == undefined){
          var svgRect = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 44 44" preserveAspectRatio="xMidYMid meet" x="955"  stroke="'+competitor.color+'"><g fill="none" fill-rule="evenodd" stroke-width="2"><circle cx="22" cy="22" r="1"><animate attributeName="r" begin="0s" dur="1.8s" values="1; 20" calcMode="spline" keyTimes="0; 1" keySplines="0.165, 0.84, 0.44, 1" repeatCount="indefinite"/><animate attributeName="stroke-opacity" begin="0s" dur="1.8s" values="1; 0" calcMode="spline" keyTimes="0; 1" keySplines="0.3, 0.61, 0.355, 1" repeatCount="indefinite"/></circle><circle cx="22" cy="22" r="1"><animate attributeName="r" begin="-0.9s" dur="1.8s" values="1; 20" calcMode="spline" keyTimes="0; 1" keySplines="0.165, 0.84, 0.44, 1" repeatCount="indefinite"/><animate attributeName="stroke-opacity" begin="-0.9s" dur="1.8s" values="1; 0" calcMode="spline" keyTimes="0; 1" keySplines="0.3, 0.61, 0.355, 1" repeatCount="indefinite"/></circle></g></svg>';
          var pulseIcon = L.icon({
            iconUrl: encodeURI("data:image/svg+xml," + svgRect).replace('#','%23'),
            iconSize: [40, 40],
            shadowSize: [40, 40],
            iconAnchor: [20, 20],
            shadowAnchor: [0, 0],
            popupAnchor: [0, 0]
          });
          competitor.mapMarker = L.marker(
            [loc.coords.latitude, loc.coords.longitude],
            {icon: pulseIcon}
          );
          competitor.mapMarker.addTo(map);
        } else {
          competitor.mapMarker.setLatLng([loc.coords.latitude, loc.coords.longitude]);
        }
        var pointX = map.latLngToContainerPoint([loc.coords.latitude, loc.coords.longitude]).x;
        var mapMiddleX = map.getSize().x / 2;
        if (pointX > mapMiddleX && !competitor.isNameOnRight && competitor.nameMarker) {
          map.removeLayer(competitor.nameMarker);
          competitor.nameMarker = null;
        } else if (pointX <= mapMiddleX && competitor.isNameOnRight && competitor.nameMarker) {
          map.removeLayer(competitor.nameMarker);
          competitor.nameMarker = null;
        };
        if(competitor.nameMarker == undefined){
          var iconHtml = '<span style="color: '+competitor.color+';">' + $('<span/>').text(competitor.short_name).html() + '</span>';
          var iconClass = 'runner-icon ' + 'runner-icon-' + getContrastYIQ(competitor.color);
          var nameTagEl = document.createElement('div');
          nameTagEl.className = iconClass;
          nameTagEl.innerHTML = iconHtml;
          document.body.appendChild(nameTagEl);
          var nameTagWidth = nameTagEl.childNodes[0].getBoundingClientRect().width;
          document.body.removeChild(nameTagEl);
          competitor.isNameOnRight = pointX > mapMiddleX;
          var runnerIcon = L.divIcon({
            className: iconClass,
            html: iconHtml,
            iconAnchor: [competitor.isNameOnRight ? nameTagWidth - 5 : 0, 0]
          });
          competitor.nameMarker = L.marker(
            [loc.coords.latitude, loc.coords.longitude],
            {icon: runnerIcon}
          );
          competitor.nameMarker.addTo(map);
        } else {
          competitor.nameMarker.setLatLng([loc.coords.latitude, loc.coords.longitude]);
        }
      }
      var tail = route.extractInterval(viewedTime - tailLength * 1e3, viewedTime);
      var hasPointInTail = route.hasPointInInterval(viewedTime - tailLength * 1e3, viewedTime);
      if(!hasPointInTail){
          if(competitor.tail) {
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
                  weight: 5
              });
              competitor.tail.addTo(map);
          } else {
              competitor.tail.setLatLngs(tailLatLng);
          }
      }
      var tail30s = route.extractInterval(viewedTime - 30 * 1e3, viewedTime);
      var hasPointInTail = route.hasPointInInterval(viewedTime - 30 * 1e3, viewedTime);
      if(!hasPointInTail){
          competitor.speedometer.text('');
      } else {
          var distance = 0;
          var prevPos = null;
          tail30s.getArray().forEach(function (pos) {
              if (prevPos && !isNaN(pos.coords.latitude)) {
                  distance += pos.distance(prevPos);
              }
              prevPos = pos;
          });
          var speed = 30 / distance * 1000;
          competitor.speedometer.text(formatSpeed(speed));
      }
    }
  })

  if(finishLinePoly) { 
    rankControl.setValues(finishLineCrosses);
  }
}

function drawFinishLineRanking () {
  
}

function formatSpeed(s){
  var min = Math.floor(s / 60);
  var sec = Math.floor(s % 60);
  if (min > 99) {
    return '';
  }
  return min + '\'' + ('0' + sec).slice(-2) + '"/km';
}

function getParameterByName(name) {
  try {
    name = name.replace(/[\[]/, "\\[").replace(/[\]]/, "\\]");
    var regex = new RegExp("[\\?&]" + name + "=([^&#]*)"),results = regex.exec(location.search);
    return results === null ? "" : decodeURIComponent(results[1].replace(/\+/g, " "));
  }
  catch(err) {
    return '';
  }
}

function addRasterMap(a, b, c, d, src, fit) {
  if (fit === undefined) {
    fit = false;
  }
  var anchors = [a, b, c, d];
  rasterMap = new L.ImageTransform(
    src,
    anchors
  ).addTo(map);
  if(fit) {
    var z = map.fitBounds(anchors);
  }
}

function centerMap (e) {
	map.panTo(e.latlng);
}

function onPressCustomMassStart (e) {
  if (!isLiveMode) {
    isRealTime = false;
    isCustomStart = true;

    $('#real_time_button').removeClass('active');
    $('#mass_start_button').removeClass('active');
    setCustomStart(e.latlng)
    currentTime = getCompetitionStartDate()-getCompetitorsMaxDuration();
    prevShownTime = currentTime;
    if (!resetMassStartContextMenuItem) {
      resetMassStartContextMenuItem = map.contextmenu.insertItem({
          text: 'Reset Mass Start',
          callback: onPressResetMassStart
      }, 2);
    }
  }
}
function onPressResetMassStart (e) {
  isRealTime=false;
  isCustomStart = false;

  currentTime = getCompetitionStartDate();
  prevShownTime = currentTime;

  if (resetMassStartContextMenuItem) {
    map.contextmenu.removeItem(resetMassStartContextMenuItem);
    resetMassStartContextMenuItem = null;
  }

  $('#real_time_button').removeClass('active');
  $('#mass_start_button').addClass('active');
}

function zoomIn (e) {
	map.zoomIn();
}

function zoomOut (e) {
	map.zoomOut();
}

function removeRasterMap() {
  if (rasterMap) {
    map.removeLayer(rasterMap);
    rasterMap = null;
  }
}

function checkNotice() {
  $.ajax()
}


function pressPlayPauseButton(e){
  e.preventDefault();
  playbackPaused = !playbackPaused;
}
  
function pressProgressBar(e){
  var perc = (e.pageX - $('#full_progress_bar').offset().left)/$('#full_progress_bar').width();
  if (isRealTime) {
    currentTime = getCompetitionStartDate()+(Math.min(clock.now(), getCompetitionEndDate())-getCompetitionStartDate())*perc;
  } else if (isCustomStart) {
    currentTime = getCompetitionStartDate() + getCompetitorsMinCustomOffset() + getCompetitorsMaxDuration(true) * perc;
  } else {
    currentTime = getCompetitionStartDate() + getCompetitorsMaxDuration() * perc;
  }
  prevShownTime = currentTime;
}
