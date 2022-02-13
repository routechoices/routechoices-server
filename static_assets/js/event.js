var alphabetizeNumber = function(integer) {
  return Number(integer)
    .toString(26)
    .split('')
    .map((c) =>
      (c.charCodeAt() > 96
        ? String.fromCharCode(c.charCodeAt() + 10)
        : String.fromCharCode(97 + parseInt(c))
      ).toUpperCase()
    )
    .join('')
}

L.Control.Ranking = L.Control.extend({
  onAdd: function(map) {
      var back = L.DomUtil.create('div', 'leaflet-bar leaflet-control leaflet-control-ranking')
      back.style.width = '205px'
      back.style.background = 'white'
      back.style.padding = '5px'
      back.style.top = ((showClusters ? 200 : 0) + 62) + 'px'
      back.style.right = '10px'
      back.style.position = 'absolute'
      back.style['max-height'] = '195px'
      back.style['overflow-y'] = 'auto'
      back.style['overflow-x'] = 'hidden'
      back.style['z-index'] = 10000
      back.style['font-size'] = '12px'
      document.body.prepend(back)
      return  L.DomUtil.create('div', 'tmp')
  },

  setValues: function(ranking) {
    var el = u('.leaflet-control-ranking')
    var out = '<h6>' + banana.i18n('ranking') + '</h6>'
    ranking.sort(function(a, b) {return getRelativeTime(a.time) - getRelativeTime(b.time)})
    ranking.forEach(function (c, i) {
      out += '<div style="clear:both;white-space:nowrap;width:200px;height:1em"><span style="float:left;display:inline-block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;width:135px;">' + (i+1) + ' <span style="color: '+ c.competitor.color +'">⬤</span> ' + u('<span/>').text(c.competitor.name).html() + '</span><span style="float:right;display:inline-block;white-space:nowrap;overflow:hidden;width:55px;font-feature-settings:tnum;font-variant-numeric:tabular-nums lining-nums;margin-right:10px">' + getProgressBarText(c.time) + '</span></div>'
    })
    if(out === '<h6>' + banana.i18n('ranking') + '</h6>') {
      out += '<p>-</p>'
    }
    if (el.html() !== out){
      el.html(out)
    }
  },

  onRemove: function(map) {
    u('.leaflet-control-ranking').remove()
    u('.tmp').remove()
  }
})

L.control.ranking = function(opts) {
  return new L.Control.Ranking(opts)
}

L.Control.Grouping = L.Control.extend({
  onAdd: function(map) {
      var back = L.DomUtil.create('div', 'leaflet-bar leaflet-control leaflet-control-grouping')
      back.style.width = '205px'
      back.style.background = 'white'
      back.style.padding = '5px'
      back.style.top = '62px'
      back.style.right = '10px'
      back.style.position = 'absolute'
      back.style['max-height'] = '195px'
      back.style['overflow-y'] = 'auto'
      back.style['overflow-x'] = 'hidden'
      back.style['z-index'] = 10000
      back.style['font-size'] = '12px'
      document.body.prepend(back)
      return  L.DomUtil.create('div', 'tmp2')
  },

  setValues: function(c, cl) {
    var el = u('.leaflet-control-grouping')
    var out = ''
    cl.forEach(function(k, i) {
      if (i!==0){
        out+='<br>'
      }
      out += '<h6>' + banana.i18n('group') + ' '+ alphabetizeNumber(i) +'</h6>'
      k.parts.forEach(function(ci) {
        out += '<div style="clear:both;white-space:nowrap;width:200px;height:1em"><span style="float:left;display:inline-block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;width:195px;"><span style="color: '+ c[ci].color +'">⬤</span> ' + u('<span/>').text(c[ci].name).html() + '</span></div>'
      })
    })
    if(out === '' ) {
      out = '<h6>' + banana.i18n('no-group') + '</h6>'
    }
    if (el.html() !== out){
      el.html(out)
    }
  },

  onRemove: function(map) {
    u('.leaflet-control-grouping').remove()
    u('.tmp2').remove()
  }
})

L.control.grouping = function(opts) {
  return new L.Control.Grouping(opts)
}

Array.prototype.findIndex = Array.prototype.findIndex || function(callback) {
  if (this === null) {
    throw new TypeError('Array.prototype.findIndex called on null or undefined')
  } else if (typeof callback !== 'function') {
    throw new TypeError('callback must be a function')
  }
  var list = Object(this)
  var length = list.length >>> 0
  var thisArg = arguments[1]
  for (var i = 0; i < length; i++) {
    if ( callback.call(thisArg, list[i], i, list) ) {
      return i
    }
  }
  return -1
}

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
  hexcolor = hexcolor.replace("#", "")
  var r = parseInt(hexcolor.substr(0,2),16)
  var g = parseInt(hexcolor.substr(2,2),16)
  var b = parseInt(hexcolor.substr(4,2),16)
  var yiq = ((r*299)+(g*587)+(b*114))/1000
  return (yiq <= 168) ? 'dark' : 'light'
}

var map = null
var isLiveMode = false
var liveUrl = null
var isLiveEvent = false
var isRealTime = true
var isCustomStart = false
var competitorList = []
var competitorRoutes = {}
var routesLastFetched = -Infinity
var noticeLastFetched = -Infinity
var fetchPositionInterval = 10
var playbackRate = 16
var playbackPaused = true
var prevDisplayRefresh = 0
var tailLength = 60
var isCurrentlyFetchingRoutes = false
var isCurrentlyFetchingNotice = false
var currentTime = 0
var lastDataTs = 0
var lastNbPoints = 0
var optionDisplayed = false
var mapHash = ''
var mapUrl = null
var rasterMap = null
var searchText = null
var noticeUrl = null
var prevNotice = new Date(0)
var resetMassStartContextMenuItem = null
var setMassStartContextMenuItem = null
var setFinishLineContextMenuItem = null
var removeFinishLineContextMenuItem = null
var clusters = {}
var qrUrl = null
var finishLineCrosses = []
var finishLinePoints = []
var finishLinePoly = null
var rankControl = null
var groupControl = null
var panControl = null
var zoomControl = null
var rotateControl = null
var showClusters = false
var showControls = true
var backdropMaps = {}
var colorModal = new bootstrap.Modal(document.getElementById("colorModal"))
var chatDisplayed = false
var chatMessages = []
var chatEventSource = null
var chatNick = ''
var zoomOnRunners = false
var clock = null
var banana = null
var sendInterval = 0
var endEvent = null
backdropMaps['blank'] = L.tileLayer('data:image/svg+xml,<svg viewBox="0 0 512 512" xmlns="http://www.w3.org/2000/svg"><rect fill="rgb(256,256,256)" width="512" height="512"/></svg>', {
  attribution: '',
  tileSize: 512
})
backdropMaps['osm'] = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  attribution: 'Map data &copy; <a href="http://openstreetmap.org">OpenStreetMap</a> contributors, <a href="http://creativecommons.org/licenses/by-sa/2.0/">CC-BY-SA</a>, Imagery © <a href="http://mapbox.com">Mapbox</a>',
})
backdropMaps['gmap-street'] = L.tileLayer('https://mt0.google.com/vt/x={x}&y={y}&z={z}', {
  attribution: '&copy; Google'
})
backdropMaps['gmap-hybrid'] = L.tileLayer('https://mt0.google.com/vt/lyrs=y&hl=en&x={x}&y={y}&z={z}', {
  attribution: '&copy; Google'
})
backdropMaps['topo-fi'] = L.tileLayer('https://tiles.kartat.kapsi.fi/peruskartta/{z}/{x}/{y}.jpg', {
  attribution: '&copy; National Land Survey of Finland'
})
backdropMaps['mapant-fi'] = L.tileLayer('https://wmts.mapant.fi/wmts_EPSG3857.php?z={z}&x={x}&y={y}', {
  attribution: '&copy; MapAnt.fi and National Land Survey of Finland'
})
backdropMaps['topo-no'] = L.tileLayer(
  'https://opencache.statkart.no/gatekeeper/gk/gk.open_gmaps?layers=topo4&zoom={z}&x={x}&y={y}', {
    attribution: ''
})
backdropMaps['mapant-no'] = L.tileLayer('https://mapant.no/osm-tiles/{z}/{x}/{y}.png', {
  attribution: '&copy; MapAnt.no'
})
backdropMaps['mapant-es'] = L.tileLayer.wms(
    'https://mapant.es/mapserv?map=/mapas/geotiff.map',
    {layers: 'geotiff', format: 'image/png', version: '1.3.0', transparent: true, attribution: '&copy; MapAnt.es'}
)
backdropMaps['topo-world'] = L.tileLayer('https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png', {
  attribution: '&copy; OpenTopoMap (CC-BY-SA)'
})

function drawFinishLine (e) {
  finishLinePoints = []
  if(finishLinePoly){
    map.removeLayer(finishLinePoly)
    map.removeControl(rankControl)
    finishLinePoly = null
  }
	finishLinePoints.push(e.latlng)
  map.on('click', drawFinishLineEnd)
}

function removeFinishLine() {
  if(finishLinePoly){
    map.removeLayer(finishLinePoly)
    map.removeControl(rankControl)
    finishLinePoly = null
    map.contextmenu.removeItem(removeFinishLineContextMenuItem)
    removeFinishLineContextMenuItem = null
    setFinishLineContextMenuItem = map.contextmenu.insertItem({
      text: banana.i18n('draw-finish-line'),
      callback: drawFinishLine
    }, 1)
  }
}

function drawFinishLineEnd(e) {
  finishLinePoints.push(e.latlng)
  finishLinePoly = L.polyline(finishLinePoints, {color: 'purple'})
  map.off('click', drawFinishLineEnd)
  rankControl = L.control.ranking({ position: 'topright' })
  map.addControl(rankControl)
  map.addLayer(finishLinePoly)
  map.contextmenu.removeItem(setFinishLineContextMenuItem)
  setFinishLineContextMenuItem = null
  removeFinishLineContextMenuItem = map.contextmenu.insertItem({
      text: banana.i18n('remove-finish-line'),
      callback: removeFinishLine
  }, 1)
}

var onStart = function(){
  if(isLiveEvent){
    selectLiveMode()
  } else {
    u("#live_button").remove()
    selectReplayMode()
  }
  fetchCompetitorRoutes()
}

var selectLiveMode = function(e){
  if(e !== undefined){
    e.preventDefault()
  }
  if(isLiveMode){
    return
  }
  if (setMassStartContextMenuItem) {
     map.contextmenu.removeItem(setMassStartContextMenuItem)
     setMassStartContextMenuItem = null
  }
  if (resetMassStartContextMenuItem) {
     map.contextmenu.removeItem(resetMassStartContextMenuItem)
     resetMassStartContextMenuItem = null
  }
  u("#live_button").addClass('active')
  u("#replay_button").removeClass('active')
  u("#replay_mode_buttons").hide()
  u("#replay_control_buttons").hide()

  isLiveMode = true
  isRealTime = true

  ;(function whileLive(){
    if (((performance.now()-routesLastFetched) > (fetchPositionInterval * 1e3)) && !isCurrentlyFetchingRoutes) {
      fetchCompetitorRoutes()
    }
    if(((performance.now() - noticeLastFetched) > (30 * 1e3)) && !isCurrentlyFetchingNotice){
      fetchNotice()
    }
    currentTime = +clock.now() - (fetchPositionInterval + 5 + sendInterval)  * 1e3 // Delay by the fetch interval (10s) + the cache interval (5sec) + the send interval (default 5sec)
    drawCompetitors()
    var isStillLive = (+endEvent >= +clock.now())
    if (!isStillLive) {
      u("#live_button").remove()
      selectReplayMode()
    }
    if (isLiveMode) {
      setTimeout(whileLive, 101)
    }
  })()
}

var selectReplayMode = function(e){
  if(e !== undefined){
    e.preventDefault()
  }
  if(!isLiveMode && u("#replay_button").hasClass('active')){
    return
  }
  u("#live_button").removeClass('active')
  u("#replay_button").addClass('active')
  u("#replay_mode_buttons").css({display:'inline-block'})
  u("#replay_control_buttons").css({display:'inline-block'})
  if (!setMassStartContextMenuItem) {
    setMassStartContextMenuItem = map.contextmenu.insertItem({
      text: banana.i18n('mass-start-from-here'),
      callback: onPressCustomMassStart
    }, 2)
  }
  isLiveMode = false
  prevShownTime = getCompetitionStartDate()
  playbackPaused = true
  prevDisplayRefresh = performance.now()
  playbackRate = 16
  ;(function whileReplay(){
    if(isLiveEvent && ((performance.now() - routesLastFetched) > (fetchPositionInterval * 1e3)) && !isCurrentlyFetchingRoutes){
      fetchCompetitorRoutes()
    }
    if(isLiveEvent && ((performance.now() - noticeLastFetched) > (30 * 1e3)) && !isCurrentlyFetchingNotice){
      fetchNotice()
    }
    var actualPlaybackRate = playbackPaused ? 0 : playbackRate

    currentTime = Math.max(getCompetitionStartDate(), prevShownTime + (performance.now() - prevDisplayRefresh) * actualPlaybackRate)
    var maxCTime = getCompetitionStartDate() + getCompetitorsMaxDuration()
    if (isCustomStart) {
      maxCTime = getCompetitionStartDate() + getCompetitorsMinCustomOffset() + getCompetitorsMaxDuration(true)
    }
    if (isRealTime) {
      maxCTime = getCompetitionStartDate() + (Math.min(+clock.now(), getCompetitionEndDate())-getCompetitionStartDate())
    }
    currentTime = Math.min(+clock.now(), currentTime, maxCTime)
    drawCompetitors()
    prevShownTime = currentTime
    prevDisplayRefresh = performance.now()
    if(!isLiveMode){
      setTimeout(whileReplay, 101)
    }
  })()
}

var fetchCompetitorRoutes = function(url){
  isCurrentlyFetchingRoutes = true
  url = url || liveUrl
  var data = {lastDataTs: Math.round(lastDataTs / fetchPositionInterval) * fetchPositionInterval}
  $.ajax({
    url: url,
    data: data,
    xhrFields: {
      withCredentials: true
   },
   crossDomain: true,
  }).done(function(response){
    var runnerPoints = []
    response.competitors.forEach(function(competitor){
      if(competitor.encoded_data) {
        var route = PositionArchive.fromEncoded(competitor.encoded_data)
        competitorRoutes[competitor.id] = route
        if(zoomOnRunners) {
          var length = route.getPositionsCount()
          for (var i = 0; i < length; i++) {
            var pt = route.getByIndex(i)
            runnerPoints.push(L.latLng([pt.coords.latitude, pt.coords.longitude]))
          }
        }
      }
    })

    updateCompetitorList(response.competitors)
    displayCompetitorList()
    routesLastFetched = performance.now()
    lastDataTs = response.timestamp
    isCurrentlyFetchingRoutes = false
    if(zoomOnRunners && runnerPoints.length) {
      map.fitBounds(runnerPoints)
    }
    u('#eventLoadingModal').remove()
  }).fail(function(){
    isCurrentlyFetchingRoutes = false
  })
}

var fetchNotice = function() {
  isCurrentlyFetchingNotice = true
  $.ajax({
    url: eventUrl,
    xhrFields: {
      withCredentials: true
   },
   crossDomain: true,
  }).done(function(response){
    noticeLastFetched = performance.now()
    isCurrentlyFetchingNotice = false
    if (response.announcement && response.announcement != prevNotice) {
      prevNotice = response.announcement
      u('#alert-text').text(prevNotice)
      u('.page-alert').show()
    } else {
      isCurrentlyFetchingNotice = false
    }
  })
}

var updateCompetitorList = function(newList) {
    newList.forEach(updateCompetitor)
}

var setCustomStart = function (latlng) {
  competitorList.forEach(function(c){
    var minDist = Infinity
    var minDistT = null
    var route = competitorRoutes[c.id]
    if(route) {
      var length = route.getPositionsCount()
      for (var i = 0; i < length; i++) {
        dist = route.getByIndex(i).distance({coords: {latitude: latlng.lat, longitude: latlng.lng}})
        if (dist < minDist) {
          minDist = dist
          minDistT = route.getByIndex(i).timestamp
        }
      }
      c.custom_offset = minDistT
    }
  })
}

var updateCompetitor = function(newData) {
    var idx = competitorList.findIndex(function(c){return c.id == newData.id})
    if (idx != -1) {
        var c = competitorList[idx]
        Object.keys(newData).forEach(function(k){
            c[k] = newData[k]
        })
        competitorList[idx] = c
    } else {
        competitorList.push(newData)
    }
}

function toggleCompetitorList(e){
  e.preventDefault()
  if(u('#sidebar').hasClass('d-none')){
    u('#sidebar').removeClass('d-none').addClass('col-12')
    u('#map').addClass('d-none').removeClass('col-12')
  }else if(!(chatDisplayed||optionDisplayed)){
    u('#sidebar').addClass('d-none').removeClass('col-12')
    u('#map').removeClass('d-none').addClass('col-12')
    map.invalidateSize()
  }
  displayCompetitorList(true)
}

var displayCompetitorList = function(force){
    if (!force && (optionDisplayed || chatDisplayed)){
      return;
    }
    optionDisplayed =false
    chatDisplayed = false
    var listDiv = u('<div id="listCompetitor"/>')
    competitorList.forEach(function(competitor, ii){
      competitor.color = competitor.color || getColor(ii)
      competitor.isShown = (typeof competitor.isShown === "undefined") ? true : competitor.isShown

      var div = u('<div class="card-body" style="padding:5px 10px 2px 10px;"/>')
      div.html('<div class="float-start color-tag" style="margin-right: 5px; cursor: pointer"><i class="media-object fa fa-circle fa-3x" style="color:' + competitor.color + '"></i></div>\
        <div><div style="white-space: nowrap; text-overflow: ellipsis; overflow: hidden;padding-left: 7px"><b>'+ u('<div/>').text(competitor.name).html() +'</b></div>\
        <div style="white-space: nowrap; text-overflow: ellipsis; overflow: hidden;">\
          <button type="button" class="toggle_competitor_btn btn btn-default btn-sm"><i class="fa fa-toggle-' + (competitor.isShown ? 'on' : 'off') + '"></i></button>\
          <button type="button" class="center_competitor_btn btn btn-default btn-sm"><i class="fa fa-map-marker"></i></button>\
          <span><small class="speedometer"></small></span>\
        </div>\
        </div>')
      var diva = u('<div class="card" style="background-color:transparent; margin-top: 3px";/>').append(div)
      u(div).find('.color-tag').on('click', function() {
        u('#colorModalLabel').text(banana.i18n('select-color-for', competitor.name))
        var color = competitor.color
        u('#color-picker').html('')
        new iro.ColorPicker('#color-picker', {color, width: 150, display: 'inline-block'}).on('color:change', function(c){
          color = c.hexString
        })
        colorModal.show()
        u('#save-color').on('click', function(){
          competitor.color = color
          colorModal.hide()
          displayCompetitorList()

          if(competitor.mapMarker) {
            map.removeLayer(competitor.mapMarker)
          }
          if(competitor.nameMarker) {
            map.removeLayer(competitor.nameMarker)
          }
          if(competitor.tail) {
            map.removeLayer(competitor.tail)
          }
          competitor.mapMarker = null
          competitor.nameMarker = null
          competitor.tail = null

          u('#save-color').off('click')
        })
      })
      u(div).find('.toggle_competitor_btn').on('click', function(e){
        e.preventDefault()
        var icon = u(this).find('i')
        if(icon.hasClass('fa-toggle-on')){
          icon.removeClass('fa-toggle-on').addClass('fa-toggle-off')
          competitor.isShown = false
          if(competitor.mapMarker) {
            map.removeLayer(competitor.mapMarker)
          }
          if(competitor.nameMarker) {
            map.removeLayer(competitor.nameMarker)
          }
          if(competitor.tail) {
            map.removeLayer(competitor.tail)
          }
          competitor.mapMarker = null
          competitor.nameMarker = null
          competitor.tail = null
          updateCompetitor(competitor)
        }else{
          icon.removeClass('fa-toggle-off').addClass('fa-toggle-on')
          competitor.isShown = true
          updateCompetitor(competitor)
        }
      })
      u(div).find('.center_competitor_btn').on('click', function(){
        zoomOnCompetitor(competitor)
      })
      if(searchText === null || searchText === '' || competitor.name.toLowerCase().search(searchText) != -1) {
        listDiv.append(diva)
      }
      competitor.div = div
      competitor.speedometer = div.find('.speedometer')
    })
    if (competitorList.length === 0) {
      var div = u('<div/>')
      var txt  = banana.i18n('no-competitors')
      div.html('<h3>' + txt+ '</h3>')
      listDiv.append(div)
    }
    if(searchText === null) {
      var mainDiv = u('<div id="competitorSidebar"/>')
      mainDiv.append(
        u('<div style="text-align:right;margin-bottom:-27px" class="d-block d-sm-none"/>').append(
          u('<button class="btn btn-default btn-sm"/>')
          .html('<i class="fa fa-times"></i>')
          .on('click', toggleCompetitorList)
        )
      )
      if(competitorList.length){
        var hideAllTxt = banana.i18n('hide-all')
        var showAllTxt = banana.i18n('show-all')
        mainDiv.append(
          '<div>' +
          '<button id="hideAllCompetitorBtn" class="btn btn-default"><i class="fa fa-eye-slash"></i> ' + hideAllTxt + '</button>' +
          '<button id="showAllCompetitorBtn" class="btn btn-default"><i class="fa fa-eye"></i> ' + showAllTxt + '</button>' +
          '</div>'
        )
      }
      u(mainDiv).find('#hideAllCompetitorBtn').on('click', function(){
        competitorList.forEach(function(competitor){
          competitor.isShown = false
          if(competitor.mapMarker) {
            map.removeLayer(competitor.mapMarker)
          }
          if(competitor.nameMarker) {
            map.removeLayer(competitor.nameMarker)
          }
          if(competitor.tail) {
            map.removeLayer(competitor.tail)
          }
          competitor.mapMarker = null
          competitor.nameMarker = null
          competitor.tail = null
          updateCompetitor(competitor)
        })
        displayCompetitorList()
      })
      u(mainDiv).find('#showAllCompetitorBtn').on('click', function(){
      competitorList.forEach(function(competitor){
        competitor.isShown = true
        updateCompetitor(competitor)
        displayCompetitorList()
      })
    })
      if(competitorList.length > 10) {
        mainDiv.append(
          u('<input class="form-control" type="search" val=""/>').on('input', filterCompetitorList).attr('placeholder', banana.i18n('search-competitors'))
        )
      }
      mainDiv.append(listDiv)
      u('#sidebar').html('')
      u('#sidebar').append(mainDiv)
    } else {
      u('#listCompetitor').remove()
      var mainDiv = u('#competitorSidebar')
      mainDiv.append(listDiv)
    }
}

var filterCompetitorList = function(e) {
    var inputVal = u(e.target).val()
    searchText = inputVal.toLowerCase()
    displayCompetitorList()
}

var displayChat = function(ev) {
    ev.preventDefault()
    optionDisplayed = false
    if(chatDisplayed) {
      chatDisplayed = false
      u('#sidebar').addClass('d-none').removeClass('col-12')
      u('#map').removeClass('d-none').addClass('col-12')
      map.invalidateSize()
      displayCompetitorList()
      return
    }
    if(u('#sidebar').hasClass('d-none')){
      u('#sidebar').removeClass('d-none').addClass('col-12')
      u('#map').addClass('d-none').removeClass('col-12')
    }
    chatDisplayed = true
    var mainDiv = u('<div/>')
    mainDiv.append(
      u('<div style="text-align:right;margin-bottom:-27px"/>').append(
        u('<button class="btn btn-default btn-sm"/>')
        .html('<i class="fa fa-times"></i>')
        .on('click', displayChat)
      )
    )
    mainDiv.append(
      u('<div/>').html(
        '<h4>' + banana.i18n('chat') + '</h4>'
      )
    )
    if (endEvent > new Date()) {
      mainDiv.append(
        u('<form id="chatForm"/>').html(
          '<label class="form-label" for="nickname">' + banana.i18n('nickname') + '</label>'+
          '<input class="form-control" name="nickname" id="chatNick" maxlength="20" />'+
          '<label class="form-label" for="message">' + banana.i18n('message') + '</label>'+
          '<input class="form-control" name="message" id="chatMessage" maxlength="100" autocomplete="off" style="margin-bottom: 3px"/>'+
          '<input class="btn btn-primary pull-right" id="chatSubmitBtn" type="submit" value="Send" />'
        ).on('submit', function(ev) {
          ev.preventDefault()
          if(u('#chatMessage').val() === '' || u('#chatNick').val() === '' || u('chatSubmitBtn').val() === banana.i18n('sending')){
            return
          }
          if (+endEvent <= +clock.now()) {
            swal({
              title: banana.i18n('chat-closed'),
              text: '',
              type: 'error',
              confirmButtonText: 'OK'
            })
            u('#chatForm').after(
              u('<div/>').html('<h4><i>' + banana.i18n('chat-closed') + '</i></h4>')
            )
            u('#chatForm').remove()
            return
          }
          u('#chatSubmitBtn').val(banana.i18n('sending'))
          $.ajax(
            {
              url: 'https:'+ chatMessagesEndpoint,
              headers: {
                'X-CSRFToken': csrfToken
              },
              data: {
                nickname: u('#chatNick').val(),
                message: u('#chatMessage').val(),
                csrfmiddlewaretoken: csrfToken
              },
              xhrFields: {
                withCredentials: true
              },
              method: 'POST',
              dataType: 'JSON',
              crossDomain: true
            }).success(function(){
              u('#chatMessage').val('')
              document.getElementById('chatMessage').focus()
            }).fail(function(){
              swal({
                title: banana.i18n('error-sending-msg'),
                text: '',
                type: 'error',
                confirmButtonText: 'OK'
              })
            }).always(function(){
              u('#chatSubmitBtn').val(banana.i18n('send'))
            })
        })
      )
    } else {
      mainDiv.append(
        u('<div/>').html('<h4><i>' + banana.i18n('chat-closed') + '</i></h4>')
      )
    }
    mainDiv.append(u('<div style="clear: both"/>').attr('id', 'messageList'))
    u('#sidebar').html('')
    u('#sidebar').append(mainDiv)
    u('#chatNick').attr('placeholder', banana.i18n('nickname'))
    u('#chatMessage').attr('placeholder', banana.i18n('message'))
    u('#chatSubmitBtn').attr('value', banana.i18n('send'))
    refreshMessageList()
    u('#chatNick').val(chatNick)
    u('#chatNick').on('change', function(ev){
      chatNick = ev.target.value
    })
}

var refreshMessageList = function() {
  var out = ''
  if(!chatEventSource){
    out = '<div><i class="fa fa-spinner fa-spin fa-2x"></i></div>'
    u('#messageList').html(out)
    return
  }
  chatMessages.sort((a, b) => b.timestamp - a.timestamp)
  chatMessages.forEach(function(msg){
    if (msg.removed) {
      out += '<div><span>' + hashAvatar(msg.user_hash, 20) + ' <i>' + banana.i18n('message-removed') + '</i></div>'
    } else {
      var div = document.createElement('div');
      var innerHTML = '<div><span>' + hashAvatar(msg.user_hash, 20) + ' <b>' + u('<span/>').text(msg.nickname).html()+'</b></span>: ' + u('<span/>').text(msg.message).html()+ '</div>'
      div.innerHTML = innerHTML;
      twemoji.parse(div, {folder: 'svg', ext: '.svg'});
      out += div.innerHTML
    }
  })
  u('#messageList').html(out)
}

var displayOptions = function(ev) {
    ev.preventDefault()
    chatDisplayed = false
    if(optionDisplayed) {
      optionDisplayed = false
      u('#sidebar').addClass('d-none').removeClass('col-12')
      u('#map').removeClass('d-none').addClass('col-12')
      map.invalidateSize()
      displayCompetitorList()
      return
    }
    if(u('#sidebar').hasClass('d-none')){
      u('#sidebar').removeClass('d-none').addClass('col-12')
      u('#map').addClass('d-none').removeClass('col-12')
    }
    optionDisplayed = true
    searchText = null
    var mainDiv = u('<div/>')
    mainDiv.append(
      u('<div style="text-align:right;margin-bottom:-27px"/>').append(
        u('<button class="btn btn-default btn-sm"/>')
        .html('<i class="fa fa-times"></i>')
        .on('click', displayOptions)
      )
    )
    var qrDataUrl = null
    if (qrUrl) {
      var qr = qrcode(0, 'L')
      qr.addData(qrUrl)
      qr.make()
      qrDataUrl = qr.createDataURL(4)
    }
    mainDiv.append(
      u('<div/>').html(
        '<h4>' + banana.i18n('tails') + '</h4>' +
        '<div class="form-group">' +
        '<label for="tailLengthInput">' + banana.i18n('length-in-seconds') +'</label>' +
        '<input type="number" min="0" class="form-control" id="tailLengthInput" value="'+ tailLength +'"/>' +
        '</div>' +
        '<h4>' + banana.i18n('map-controls') + '</h4>' +
        '<button type="button" class="toggle_controls_btn btn btn-default btn-sm"><i class="fa fa-toggle-' + (showControls ? 'on' : 'off') + '"></i> ' + banana.i18n('show-map-controls') + '</button>' +
        '<h4>' + banana.i18n('groupings') + '</h4>' +
        '<button type="button" class="toggle_cluster_btn btn btn-default btn-sm"><i class="fa fa-toggle-' + (showClusters ? 'on' : 'off') + '"></i> ' + banana.i18n('show-groupings') + '</button>' +
        '<h4><i class="fa fa-language"></i> ' + banana.i18n('language') + '</h4>' +
        '<select class="form-select" id="languageSelector">' +
        Object.keys(supportedLanguages).map(function(l) {
          return '<option value="' + l + '"' + (locale === l ? ' selected' : '') + '>' + supportedLanguages[l] + '</option>'
        }).join('') +
        '</select>' +
        (qrUrl ? ('<h4>' + banana.i18n('qr-link') + '</h4><p style="text-align:center"><img style="margin-bottom:15px" src="' + qrDataUrl + '" alt="qr"><br/><a class="small" href="'+ qrUrl +'">'+qrUrl.replace(/^https?:\/\//, '')+'</a></p>') : '')
      )
    )
    u(mainDiv).find('#languageSelector').on('change', function(e) {
      window.localStorage.setItem('lang', e.target.value)
      window.location.reload()
    })
    u(mainDiv).find('#tailLengthInput').on('input', function(e){
      var v = parseInt(e.target.value)
      if (isNaN(v)) {
        v = 0
      }
      tailLength = Math.max(0, v)
    })
    u(mainDiv).find('.toggle_cluster_btn').on('click', function(e){
      if (showClusters){
        u('.toggle_cluster_btn')
          .find('.fa-toggle-on')
          .removeClass('fa-toggle-on')
          .addClass('fa-toggle-off')
        showClusters = false
        map.removeControl(groupControl)
        u('.leaflet-control-ranking').css({top: '62px'})
      } else {
        u('.toggle_cluster_btn')
          .find('.fa-toggle-off')
          .removeClass('fa-toggle-off')
          .addClass('fa-toggle-on')
        groupControl = L.control.grouping({ position: 'topright' })
        map.addControl(groupControl)
        showClusters = true
        u('.leaflet-control-ranking').css({top: '262px'})
      }
    })
    u(mainDiv).find('.toggle_controls_btn').on('click', function(e){
      if (showControls){
        u('.toggle_controls_btn')
          .find('.fa-toggle-on')
          .removeClass('fa-toggle-on')
          .addClass('fa-toggle-off')
        showControls = false
        map.removeControl(panControl)
        map.removeControl(zoomControl)
        map.removeControl(rotateControl)
      } else {
        u('.toggle_controls_btn')
          .find('.fa-toggle-off')
          .removeClass('fa-toggle-off')
          .addClass('fa-toggle-on')
        map.addControl(panControl)
        map.addControl(zoomControl)
        map.addControl(rotateControl)
        showControls = true
      }
    })
    u('#sidebar').html('')
    u('#sidebar').append(mainDiv)
}

var getCompetitionStartDate = function() {
    var res = +clock.now()
    competitorList.forEach(function(c){
        var route = competitorRoutes[c.id]
        if(route) {
            res = res > route.getByIndex(0).timestamp ? route.getByIndex(0).timestamp : res
        }
    })
    return res
}
var getCompetitionEndDate = function() {
    var res = new Date(0)
    competitorList.forEach(function(c){
        var route = competitorRoutes[c.id]
        if(route) {
            var idx = route.getPositionsCount()-1
            res = res<route.getByIndex(idx).timestamp?route.getByIndex(idx).timestamp: res
        }
    })
    return res
}
var getCompetitorsMaxDuration = function(customOffset) {
    if(customOffset === undefined) {
      customOffset = false
    }
    var res = 0
    competitorList.forEach(function(c){
        var route = competitorRoutes[c.id]
        if(route) {
            var idx = route.getPositionsCount()-1

            var dur = route.getByIndex(idx).timestamp - ((customOffset ? +new Date(c.custom_offset) : +new Date(c.start_time)) || getCompetitionStartDate())
            res = res < dur ? dur : res
        }
    })
    return res
}
var getCompetitorsMinCustomOffset = function() {
    var res = 0
    competitorList.forEach(function(c){
        var route = competitorRoutes[c.id]
        if(route) {
          var off = (c.custom_offset - c.start_time) || 0
          res = res < off ? off : res
        }
    })
    return res
}

var zoomOnCompetitor = function(compr){
  var route = competitorRoutes[compr.id]
  if(!route) return
  var timeT = currentTime
  if(!isRealTime){
    if (isCustomStart) {
      timeT += +new Date(compr.custom_offset) - getCompetitionStartDate()
    } else {
      timeT += +new Date(compr.start_time) - getCompetitionStartDate()
    }
  }
  var loc = route.getByTime(timeT)
  map.setView([loc.coords.latitude, loc.coords.longitude])
}
var getRelativeTime = function(currentTime) {
  var viewedTime = currentTime
  if (!isRealTime) {
      if (isCustomStart) {
        viewedTime -= getCompetitorsMinCustomOffset() + getCompetitionStartDate()
      } else {
        viewedTime -= getCompetitionStartDate()
      }
  }
  return viewedTime
}
var getProgressBarText = function(currentTime){
    var result = ''
    var viewedTime = currentTime
    if (!isRealTime) {
        if (isCustomStart) {
          viewedTime -= getCompetitorsMinCustomOffset() + getCompetitionStartDate()
        } else {
          viewedTime -= getCompetitionStartDate()
        }
        var t = viewedTime / 1e3

        to2digits = function(x){return ('0'+Math.floor(x)).slice(-2)},
        result += t > 3600 ? Math.floor(t/3600) + ':': ''
        result += to2digits((t / 60) % 60) + ':' + to2digits(t % 60)
    } else {
        if(viewedTime === 0) {
          return '00:00:00'
        }
        result = dayjs(viewedTime).format('HH:mm:ss')
    }
    return result
}
var drawCompetitors = function(){
  // play/pause button
  if(playbackPaused){
    var html = '<i class="fa fa-play"></i> x' + playbackRate
    if(u('#play_pause_button').html() != html){
      u('#play_pause_button').html(html)
    }
  } else {
    var html = '<i class="fa fa-pause"></i> x' + playbackRate
    if(u('#play_pause_button').html() != html){
      u('#play_pause_button').html(html)
    }
  }
  // progress bar
  var perc = 0
  if (isRealTime) {
    perc = isLiveMode ? 100 : (currentTime-getCompetitionStartDate())/(Math.min(+clock.now(), getCompetitionEndDate())-getCompetitionStartDate()) * 100
  } else {
    if (isCustomStart) {
      perc = (currentTime - (getCompetitionStartDate()+getCompetitorsMinCustomOffset())) / getCompetitorsMaxDuration(true) * 100
    } else {
      perc = (currentTime - getCompetitionStartDate()) / getCompetitorsMaxDuration() * 100
    }
  }
  u('#progress_bar').css({width: perc+'%'}).attr('aria-valuenow', perc)
  u('#progress_bar_text').html(getProgressBarText(currentTime))
  var oldFinishCrosses = finishLineCrosses.slice()
  finishLineCrosses = []
  competitorList.forEach(function(competitor){
    if(!competitor.isShown){
      return;
    }
    var route = competitorRoutes[competitor.id]
    if(route !== undefined){
      var viewedTime = currentTime
      if(!isLiveMode && !isRealTime && !isCustomStart && competitor.start_time){
        viewedTime += Math.max(0, new Date(competitor.start_time) - getCompetitionStartDate())
      }
      if(!isLiveMode && !isRealTime && isCustomStart && competitor.custom_offset){
        viewedTime += Math.max(0, new Date(competitor.custom_offset) - getCompetitionStartDate())
      }
      if(finishLinePoly) {
        var allPoints = route.getArray()
        var oldCrossing = oldFinishCrosses.find(function(el){return el.competitor.id === competitor.id})
        var useOldCrossing = false
        if (oldCrossing) {
          var oldTs = allPoints[oldCrossing.idx].timestamp
          if (viewedTime >= oldTs) {
            if (L.LineUtil.segmentsIntersect(
              map.project(finishLinePoints[0], 16),
              map.project(finishLinePoints[1], 16),
              map.project(L.latLng([allPoints[oldCrossing.idx].coords.latitude, allPoints[oldCrossing.idx].coords.longitude]), 16),
              map.project(L.latLng([allPoints[oldCrossing.idx-1].coords.latitude, allPoints[oldCrossing.idx-1].coords.longitude]), 16)
            )
            ) {
              var competitorTime = allPoints[oldCrossing.idx].timestamp
              if(!isLiveMode && !isRealTime && !isCustomStart && competitor.start_time){
                competitorTime -= Math.max(0, new Date(competitor.start_time) - getCompetitionStartDate())
              }
              if(!isLiveMode && !isRealTime && isCustomStart && competitor.custom_offset){
                competitorTime -= Math.max(0, new Date(competitor.custom_offset) - getCompetitionStartDate())
              }
              if (getRelativeTime(competitorTime) > 0) {
                finishLineCrosses.push({
                  competitor: competitor,
                  time: competitorTime,
                  idx: oldCrossing.idx
                })
                useOldCrossing = true
              }
            }
          }
        }
        if(!useOldCrossing) {
          for (var i=1; i < allPoints.length; i++) {
            var tPoint = allPoints[i]
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
              var competitorTime = tPoint.timestamp
              if(!isLiveMode && !isRealTime && !isCustomStart && competitor.start_time){
                competitorTime -= Math.max(0, new Date(competitor.start_time) - getCompetitionStartDate())
              }
              if(!isLiveMode && !isRealTime && isCustomStart && competitor.custom_offset){
                competitorTime -= Math.max(0, new Date(competitor.custom_offset) - getCompetitionStartDate())
              }
              if (getRelativeTime(competitorTime) > 0) {
                finishLineCrosses.push({
                  competitor: competitor,
                  time: competitorTime,
                  idx: i
                })
                break
              }
            }
          }
        }
      }
      var hasPointLast30sec = route.hasPointInInterval(viewedTime - 30 * 1e3, viewedTime)
      var loc = route.getByTime(viewedTime)
      if(!hasPointLast30sec){
        if (!competitor.idle) {
          if(competitor.mapMarker) {
            map.removeLayer(competitor.mapMarker)
          }
          if(competitor.nameMarker) {
            map.removeLayer(competitor.nameMarker)
          }
          competitor.mapMarker = null
          competitor.nameMarker = null
          competitor.idle = true
        }
        if (loc && !isNaN(loc.coords.latitude)) {
          var ccolor = tinycolor(competitor.color).setAlpha(.4)
          if(competitor.mapMarker == undefined){
            var svgRect = '<svg viewBox="0 0 8 8" xmlns="http://www.w3.org/2000/svg"><circle fill="' + ccolor.toRgbString() + '" cx="4" cy="4" r="3"/></svg>'
            var pulseIcon = L.icon({
              iconUrl: encodeURI("data:image/svg+xml," + svgRect),
              iconSize: [8, 8],
              shadowSize: [8, 8],
              iconAnchor: [4, 4],
              shadowAnchor: [0, 0],
              popupAnchor: [0, 0]
            })
            competitor.mapMarker = L.marker(
              [loc.coords.latitude, loc.coords.longitude],
              {icon: pulseIcon}
            )
            competitor.mapMarker.addTo(map)
          } else {
            competitor.mapMarker.setLatLng([loc.coords.latitude, loc.coords.longitude])
          }
          var pointX = map.latLngToContainerPoint([loc.coords.latitude, loc.coords.longitude]).x
          var mapMiddleX = map.getSize().x / 2
          if (pointX > mapMiddleX && !competitor.isNameOnRight && competitor.nameMarker) {
            map.removeLayer(competitor.nameMarker)
            competitor.nameMarker = null
          } else if (pointX <= mapMiddleX && competitor.isNameOnRight && competitor.nameMarker) {
            map.removeLayer(competitor.nameMarker)
            competitor.nameMarker = null
          }
          if(competitor.nameMarker == undefined){

            var iconHtml = '<span style="opacity: 0.4;color: ' + competitor.color + '">' + u('<span/>').text(competitor.short_name).html() + '</span>'
            var iconClass = 'runner-icon ' + 'runner-icon-' + getContrastYIQ(competitor.color)
            var nameTagEl = document.createElement('div')
            nameTagEl.className = iconClass
            nameTagEl.innerHTML = iconHtml
            document.body.appendChild(nameTagEl)
            var nameTagWidth = nameTagEl.childNodes[0].getBoundingClientRect().width
            document.body.removeChild(nameTagEl)
            competitor.isNameOnRight = pointX > mapMiddleX
            var runnerIcon = L.divIcon({
              className: iconClass,
              html: iconHtml,
              iconAnchor: [competitor.isNameOnRight ? nameTagWidth - 5 : 0, 0]
            })
            competitor.nameMarker = L.marker(
              [loc.coords.latitude, loc.coords.longitude],
              {icon: runnerIcon}
            )
            competitor.nameMarker.addTo(map)
          } else {
            competitor.nameMarker.setLatLng([loc.coords.latitude, loc.coords.longitude])
          }
        }
      }
      if(loc && !isNaN(loc.coords.latitude) && hasPointLast30sec){
        if (competitor.idle) {
          if(competitor.mapMarker) {
            map.removeLayer(competitor.mapMarker)
          }
          if(competitor.nameMarker) {
            map.removeLayer(competitor.nameMarker)
          }
          competitor.mapMarker = null
          competitor.nameMarker = null
          competitor.idle = false
        }

        if(competitor.mapMarker == undefined){
          var svgRect = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 44 44" preserveAspectRatio="xMidYMid meet" x="955"  stroke="'+competitor.color+'"><g fill="none" fill-rule="evenodd" stroke-width="2"><circle cx="22" cy="22" r="1"><animate attributeName="r" begin="0s" dur="1.8s" values="1; 20" calcMode="spline" keyTimes="0; 1" keySplines="0.165, 0.84, 0.44, 1" repeatCount="indefinite"/><animate attributeName="stroke-opacity" begin="0s" dur="1.8s" values="1; 0" calcMode="spline" keyTimes="0; 1" keySplines="0.3, 0.61, 0.355, 1" repeatCount="indefinite"/></circle><circle cx="22" cy="22" r="1"><animate attributeName="r" begin="-0.9s" dur="1.8s" values="1; 20" calcMode="spline" keyTimes="0; 1" keySplines="0.165, 0.84, 0.44, 1" repeatCount="indefinite"/><animate attributeName="stroke-opacity" begin="-0.9s" dur="1.8s" values="1; 0" calcMode="spline" keyTimes="0; 1" keySplines="0.3, 0.61, 0.355, 1" repeatCount="indefinite"/></circle></g></svg>'
          var pulseIcon = L.icon({
            iconUrl: encodeURI("data:image/svg+xml," + svgRect).replace('#','%23'),
            iconSize: [40, 40],
            shadowSize: [40, 40],
            iconAnchor: [20, 20],
            shadowAnchor: [0, 0],
            popupAnchor: [0, 0]
          })
          competitor.mapMarker = L.marker(
            [loc.coords.latitude, loc.coords.longitude],
            {icon: pulseIcon}
          )
          competitor.mapMarker.addTo(map)
        } else {
          competitor.mapMarker.setLatLng([loc.coords.latitude, loc.coords.longitude])
        }
        var pointX = map.latLngToContainerPoint([loc.coords.latitude, loc.coords.longitude]).x
        var mapMiddleX = map.getSize().x / 2
        if (pointX > mapMiddleX && !competitor.isNameOnRight && competitor.nameMarker) {
          map.removeLayer(competitor.nameMarker)
          competitor.nameMarker = null
        } else if (pointX <= mapMiddleX && competitor.isNameOnRight && competitor.nameMarker) {
          map.removeLayer(competitor.nameMarker)
          competitor.nameMarker = null
        }
        if(competitor.nameMarker == undefined){
          var iconHtml = '<span style="color: '+competitor.color+'">' + u('<span/>').text(competitor.short_name).html() + '</span>'
          var iconClass = 'runner-icon ' + 'runner-icon-' + getContrastYIQ(competitor.color)
          var nameTagEl = document.createElement('div')
          nameTagEl.className = iconClass
          nameTagEl.innerHTML = iconHtml
          document.body.appendChild(nameTagEl)
          var nameTagWidth = nameTagEl.childNodes[0].getBoundingClientRect().width
          document.body.removeChild(nameTagEl)
          competitor.isNameOnRight = pointX > mapMiddleX
          var runnerIcon = L.divIcon({
            className: iconClass,
            html: iconHtml,
            iconAnchor: [competitor.isNameOnRight ? nameTagWidth - 5 : 0, 0]
          })
          competitor.nameMarker = L.marker(
            [loc.coords.latitude, loc.coords.longitude],
            {icon: runnerIcon}
          )
          competitor.nameMarker.addTo(map)
        } else {
          competitor.nameMarker.setLatLng([loc.coords.latitude, loc.coords.longitude])
        }
      }
      var tail = route.extractInterval(viewedTime - tailLength * 1e3, viewedTime)
      var hasPointInTail = route.hasPointInInterval(viewedTime - tailLength * 1e3, viewedTime)
      if(!hasPointInTail){
          if(competitor.tail) {
            map.removeLayer(competitor.tail)
          }
          competitor.tail = null
      } else {
          var tailLatLng = []
          tail.getArray().forEach(function (pos) {
              if (!isNaN(pos.coords.latitude)) {
                  tailLatLng.push([pos.coords.latitude, pos.coords.longitude])
              }
          })
          if (competitor.tail == undefined) {
              competitor.tail = L.polyline(tailLatLng, {
                  color: competitor.color,
                  opacity: 0.75,
                  weight: 5
              })
              competitor.tail.addTo(map)
          } else {
              competitor.tail.setLatLngs(tailLatLng)
          }
      }
      var tail30s = route.extractInterval(viewedTime - 30 * 1e3, viewedTime)
      var hasPointInTail = route.hasPointInInterval(viewedTime - 30 * 1e3, viewedTime)
      if(!hasPointInTail){
          competitor.speedometer.text('')
      } else {
          var distance = 0
          var prevPos = null
          tail30s.getArray().forEach(function (pos) {
              if (prevPos && !isNaN(pos.coords.latitude)) {
                  distance += pos.distance(prevPos)
              }
              prevPos = pos
          })
          var speed = 30 / distance * 1000
          competitor.speedometer.text(formatSpeed(speed))
      }
    }
  })

  // Create cluster
  if(showClusters) {
    var listCompWithMarker = []
    var gpsPointData = []
    competitorList.forEach(function(competitor){
      if (competitor.mapMarker){
        listCompWithMarker.push(competitor)
        var latLon = competitor.mapMarker.getLatLng()
        gpsPointData.push({
          location: {
            accuracy: 0,
            latitude: latLon.lat,
            longitude: latLon.lng
          }
        })
      }
    })
    var dbscanner = jDBSCAN()
      .eps(0.015)
      .minPts(1)
      .distance('HAVERSINE')
      .data(gpsPointData)
    var gpsPointAssignmentResult = dbscanner()
    var clusterCenters = dbscanner.getClusters()

    Object.keys(clusters).forEach(function(k) {
      if (gpsPointAssignmentResult.indexOf(k) === -1) {
        if (clusters[k].mapMarker) {
          map.removeLayer(clusters[k].mapMarker)
          clusters[k].mapMarker = null
        }
        if (clusters[k].nameMarker) {
          map.removeLayer(clusters[k].nameMarker)
          clusters[k].nameMarker = null
        }
      }
    })

    gpsPointAssignmentResult.forEach(function(d, i) {
      if (d != 0) {
        var cluster = clusters[d] || {}
        var clusterCenter = clusterCenters[d-1]
        if (!cluster.color) {
          cluster.color = getColor(i)
        }
        var c = listCompWithMarker[i]
        if(c.mapMarker) {
          map.removeLayer(c.mapMarker)
          c.mapMarker = null
        }
        if(c.nameMarker) {
          map.removeLayer(c.nameMarker)
          c.nameMarker = null
        }
        if (cluster.mapMarker) {
          cluster.mapMarker.setLatLng([clusterCenter.location.latitude, clusterCenter.location.longitude])
        } else {
          var svgRect = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 44 44" preserveAspectRatio="xMidYMid meet" x="955"  stroke="'+cluster.color+'"><g fill="none" fill-rule="evenodd" stroke-width="2"><circle cx="22" cy="22" r="1"><animate attributeName="r" begin="0s" dur="1.8s" values="1; 20" calcMode="spline" keyTimes="0; 1" keySplines="0.165, 0.84, 0.44, 1" repeatCount="indefinite"/><animate attributeName="stroke-opacity" begin="0s" dur="1.8s" values="1; 0" calcMode="spline" keyTimes="0; 1" keySplines="0.3, 0.61, 0.355, 1" repeatCount="indefinite"/></circle><circle cx="22" cy="22" r="1"><animate attributeName="r" begin="-0.9s" dur="1.8s" values="1; 20" calcMode="spline" keyTimes="0; 1" keySplines="0.165, 0.84, 0.44, 1" repeatCount="indefinite"/><animate attributeName="stroke-opacity" begin="-0.9s" dur="1.8s" values="1; 0" calcMode="spline" keyTimes="0; 1" keySplines="0.3, 0.61, 0.355, 1" repeatCount="indefinite"/></circle></g></svg>'
          var pulseIcon = L.icon({
            iconUrl: encodeURI("data:image/svg+xml," + svgRect).replace('#','%23'),
            iconSize: [40, 40],
            shadowSize: [40, 40],
            iconAnchor: [20, 20],
            shadowAnchor: [0, 0],
            popupAnchor: [0, 0]
          })
          cluster.mapMarker = L.marker(
            [clusterCenter.location.latitude, clusterCenter.location.longitude],
            {icon: pulseIcon}
          )
          cluster.mapMarker.addTo(map)
        }

        var pointX = map.latLngToContainerPoint([clusterCenter.location.latitude, clusterCenter.location.longitude]).x
        var mapMiddleX = map.getSize().x / 2
        if (pointX > mapMiddleX && !cluster.isNameOnRight && cluster.nameMarker) {
          map.removeLayer(cluster.nameMarker)
          cluster.nameMarker = null
        } else if (pointX <= mapMiddleX && cluster.isNameOnRight && cluster.nameMarker) {
          map.removeLayer(cluster.nameMarker)
          cluster.nameMarker = null
        }

        if (cluster.nameMarker) {
          cluster.nameMarker.setLatLng([clusterCenter.location.latitude, clusterCenter.location.longitude])
        } else {
          var iconHtml = '<span style="color: '+cluster.color+'">Group ' + alphabetizeNumber(d - 1) +'</span>'
          var iconClass = 'runner-icon ' + 'runner-icon-' + getContrastYIQ(cluster.color)
          var nameTagEl = document.createElement('div')
          nameTagEl.className = iconClass
          nameTagEl.innerHTML = iconHtml
          document.body.appendChild(nameTagEl)
          var nameTagWidth = nameTagEl.childNodes[0].getBoundingClientRect().width
          document.body.removeChild(nameTagEl)
          cluster.isNameOnRight = pointX > mapMiddleX
          var runnerIcon = L.divIcon({
            className: iconClass,
            html: iconHtml,
            iconAnchor: [cluster.isNameOnRight ? nameTagWidth - 5 : 0, 0]
          })
          cluster.nameMarker = L.marker(
            [clusterCenter.location.latitude, clusterCenter.location.longitude],
            {icon: runnerIcon}
          )
          cluster.nameMarker.addTo(map)
        }
        clusters[d] = cluster
      } else {

      }
    })

    groupControl.setValues(listCompWithMarker, clusterCenters)
  }
  if(finishLinePoly) {
    rankControl.setValues(finishLineCrosses)
  }
}

function formatSpeed(s){
  var min = Math.floor(s / 60)
  var sec = Math.floor(s % 60)
  if (min > 99) {
    return ''
  }
  return min + '\'' + ('0' + sec).slice(-2) + '"/km'
}

function getParameterByName(name) {
  try {
    name = name.replace(/[\[]/, "\\[").replace(/[\]]/, "\\]")
    var regex = new RegExp("[\\?&]" + name + "=([^&#]*)"),results = regex.exec(location.search)
    return results === null ? "" : decodeURIComponent(results[1].replace(/\+/g, " "))
  }
  catch(err) {
    return ''
  }
}

function addRasterMap(bounds, src, fit) {
  if (fit === undefined) {
    fit = false
  }
  rasterMap = L.tileLayer.wms(wmsService+'?', {
    layers: eventId,
    bounds: bounds,
    tileSize: 512,
    noWrap: true,
    format: hasWebpSupport ? 'image/webp' : 'image/png'
  }).addTo(map)
  if(fit) {
    map.fitBounds(bounds)
  }
}

function centerMap (e) {
	map.panTo(e.latlng)
}

function onPressCustomMassStart (e) {
  if (!isLiveMode) {
    isRealTime = false
    isCustomStart = true

    u('#real_time_button').removeClass('active')
    u('#mass_start_button').removeClass('active')
    setCustomStart(e.latlng)
    currentTime = getCompetitionStartDate()-getCompetitorsMaxDuration()
    prevShownTime = currentTime
    if (!resetMassStartContextMenuItem) {
      resetMassStartContextMenuItem = map.contextmenu.insertItem({
          text: banana.i18n('reset-mass-start'),
          callback: onPressResetMassStart
      }, 2)
    }
  }
}
function onPressResetMassStart (e) {
  isRealTime=false
  isCustomStart = false

  currentTime = getCompetitionStartDate()
  prevShownTime = currentTime

  if (resetMassStartContextMenuItem) {
    map.contextmenu.removeItem(resetMassStartContextMenuItem)
    resetMassStartContextMenuItem = null
  }

  u('#real_time_button').removeClass('active')
  u('#mass_start_button').addClass('active')
}

function zoomIn (e) {
	map.zoomIn()
}

function zoomOut (e) {
	map.zoomOut()
}

function removeRasterMap() {
  if (rasterMap) {
    map.removeLayer(rasterMap)
    rasterMap = null
  }
}

function pressPlayPauseButton(e){
  e.preventDefault()
  playbackPaused = !playbackPaused
}

function pressProgressBar(e){
  var perc = (e.pageX - document.getElementById('full_progress_bar').offsetLeft) / u('#full_progress_bar').size().width
  if (isRealTime) {
    currentTime = getCompetitionStartDate()+(Math.min(clock.now(), getCompetitionEndDate())-getCompetitionStartDate()) * perc
  } else if (isCustomStart) {
    currentTime = getCompetitionStartDate() + getCompetitorsMinCustomOffset() + getCompetitorsMaxDuration(true) * perc
  } else {
    currentTime = getCompetitionStartDate() + getCompetitorsMaxDuration() * perc
  }
  prevShownTime = currentTime
}

var connectChatAttempts
var connectChatTimeoutMs

function resetChatConnectTimeout() {
  connectChatAttempts = 0
  connectChatTimeoutMs = 100
}
resetChatConnectTimeout()

function bumpChatConnectTimeout() {
  connectChatAttempts++

  if (connectChatTimeoutMs === 100 && connectChatAttempts === 20) {
    connectChatAttempts = 0
    connectChatTimeoutMs = 300
  } else if (connectChatTimeoutMs === 300 && connectChatAttempts === 20) {
    connectChatAttempts = 0
    connectChatTimeoutMs = 1000
  } else if (connectChatTimeoutMs === 1000 && connectChatAttempts === 20) {
    connectChatAttempts = 0
    connectChatTimeoutMs = 3000
  }
  if (connectChatAttempts === 0) {
    console.debug(
      "😅 chat connection error, retrying every " +
        connectChatTimeoutMs +
        "ms"
    )
  }
}

function connectToChatEvents() {
  chatEventSource = new EventSource(chatStreamUrl, {withCredentials: true})
  // Listen for messages
  chatEventSource.addEventListener('open', function () {
    chatMessages = []
  })
  chatEventSource.addEventListener('message', function (event) {
    resetChatConnectTimeout()
    const message = JSON.parse(event.data)
    if (message.type === "ping") {
      // pass
    } else if (message.type === "message") {
      chatMessages.push(message)
      refreshMessageList()
    } else if (message.type === "delete") {
      chatMessages = chatMessages.map(function(msg) {if(msg.uuid === message.uuid){msg.removed = true}return msg})
      refreshMessageList()
    }
  })
  chatEventSource.addEventListener('error', function(){
    chatEventSource.close()
    chatEventSource = null
    bumpChatConnectTimeout()
    setTimeout(connectToChatEvents, connectChatTimeoutMs)
  })
}

function shareUrl (e) {
  e.preventDefault()
  var shareData = {
    title: u('meta[property="og:title"]').attr('content'),
    text: u('meta[property="og:description"]').attr('content'),
    url: window.location
  }
  try {
    navigator.share(shareData).then(function () {}).catch(function () {})
  } catch(err) {
  }
}


function updateText () {
    banana.setLocale(locale)
    var langFile = `${staticRoot}i18n/club/event/${locale}.json`
    return fetch(`${langFile}?20220020700`).then((response) => response.json()).then((messages) => {
      banana.load(messages, banana.locale)
    })
}
