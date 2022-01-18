var dataset = document.currentScript.dataset
var eventId = dataset.eventId
var eventUrl = dataset.eventUrl
var wmsService = dataset.wmsServiceUrl
var chatStreamUrl = dataset.chatStreamUrl
var chatMessagesEndpoint = dataset.chatMessagesEndpoint
var clock = ServerClock({url: dataset.serverClockUrl})
var clubName = dataset.clubName
var staticRoot = dataset.staticRoot

if (!navigator.canShare) {
  u('#share_buttons').hide()
}

function checkImageFormatCapability(format) {
  return new Promise(function(res) {
    var kTestImages = {
        webp: "data:image/webp;base64,UklGRkoAAABXRUJQVlA4WAoAAAAQAAAAAAAAAAAAQUxQSAwAAAARBxAR/Q9ERP8DAABWUDggGAAAABQBAJ0BKgEAAQAAAP4AAA3AAP7mtQAAAA==",
        avif: 'data:image/avif;base64,AAAAFGZ0eXBhdmlmAAAAAG1pZjEAAACgbWV0YQAAAAAAAAAOcGl0bQAAAAAAAQAAAB5pbG9jAAAAAEQAAAEAAQAAAAEAAAC8AAAAGwAAACNpaW5mAAAAAAABAAAAFWluZmUCAAAAAAEAAGF2MDEAAAAARWlwcnAAAAAoaXBjbwAAABRpc3BlAAAAAAAAAAQAAAAEAAAADGF2MUOBAAAAAAAAFWlwbWEAAAAAAAAAAQABAgECAAAAI21kYXQSAAoIP8R8hAQ0BUAyDWeeUy0JG+QAACANEkA='
    }
    var img = new Image()
    img.onload = function () {
        var result = (img.width > 0) && (img.height > 0)
        res(result)
    }
    img.onerror = function () {
        res(false)
    }
    img.src = kTestImages[format]
  })
}

var hasWebpSupport = false
var hasAvifSupport = false

;(function (){
  checkImageFormatCapability('webp').then(function(res){hasWebpSupport = res})
  checkImageFormatCapability('avif').then(function(res){hasAvifSupport = res})
})()

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

var browserLanguage = navigator.language.slice(0, 2)
var supportedLanguages = {
  'en': "English",
  'fr': "Français",
  'nl': "Nederlands",
  'fi': "Suomi"
}
var locale = window.localStorage.getItem('lang') || (Object.keys(supportedLanguages).includes(browserLanguage) ? browserLanguage : 'en')
const banana = new Banana()

function updateText () {
    banana.setLocale(locale)
    var langFile = `${staticRoot}i18n/club/event/${locale}.json`
    return fetch(`${langFile}?2022011600`).then((response) => response.json()).then((messages) => {
      banana.load(messages, banana.locale)
    })
}

;(function() {
  updateText().then(function(){
    u('#heads-up-text').text(banana.i18n('heads-up-text'))
    u('#chat-btn-text').text(banana.i18n('chat'))
    u('#loading-text').text(banana.i18n('loading-text'))
    u('#event-not-started-text').text(banana.i18n('event-not-started-text'))
    u('#club-events-link-text').text(banana.i18n('club-events-link-text', clubName))


    u('.page-alerts').hide()
    u('.page-alert .close').on('click', function(e) {
      e.preventDefault()
      u(this).closest('.page-alert').hide()
    })

    var thumb = document.querySelector('#full_progress_bar')
    thumb.onmousedown = function(event) {
        event.preventDefault()
        document.addEventListener('mousemove', pressProgressBar)
        function onMouseUp() {
          document.removeEventListener('mouseup', onMouseUp)
          document.removeEventListener('mousemove', pressProgressBar)
        }
        document.addEventListener('mouseup', onMouseUp)
    }
    thumb.ondragstart = function() {
        return false
    }

    u('.date-utc').each(function(el){
      $el = u(el)
      $el.text(dayjs($el.data('date')).local().locale(locale).format('LLLL'))
    })
    var startDateTxt = u('#event-start-date-text').find('.date-utc').text()
    u('#event-start-date-text').text(banana.i18n('event-start-date-text', startDateTxt))

    map = L.map('map', {
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
          text: banana.i18n('center-map'),
          callback: centerMap
        }, '-', {
          text: banana.i18n('zoom-in'),
          callback: zoomIn
        }, {
          text: banana.i18n('zoom-out'),
          callback: zoomOut
        }
      ]
    })
    panControl = L.control.pan()
    zoomControl = L.control.zoom()
    rotateControl = L.control.rotate({closeOnZeroBearing: false})

    panControl.addTo(map)
    zoomControl.addTo(map)
    rotateControl.addTo(map)

    map.doubleClickZoom.disable()
    map.on('dblclick', onPressCustomMassStart)
    map.on('move', function () { drawCompetitors() })

    $.ajax({
      url: eventUrl,
      xhrFields: {
        withCredentials: true
    },
    crossDomain: true,
    }).done(function(response){
      backdropMaps[response.event.backdrop].addTo(map)
      var now = new Date()
      var startEvent = new Date(response.event.start_date)
      var endEvent = new Date(response.event.end_date)
      if (startEvent > now) {
        u('.event-tool').hide()

        map.fitWorld({ animate: false }).zoomIn(null, { animate:false })
        u('#eventLoadingModal').remove()
        var preRaceModal = new bootstrap.Modal(document.getElementById("eventNotStartedModal"), {backdrop:'static', keyboard: false, })
        document.getElementById("eventNotStartedModal").addEventListener('hide.bs.modal', function(e){
            e.preventDefault()
        })
        preRaceModal.show()
        window.setInterval(function(){
          if(new Date() > startEvent) {
            location.reload()
          }
        }, 1e3)
      } else {
        u('#runners_show_button').on('click', toggleCompetitorList)
        u('#live_button').on('click', selectLiveMode).text(banana.i18n('live-mode'))
        u('#replay_button').on('click', selectReplayMode).text(banana.i18n('replay-mode'))
        u('#play_pause_button').on('click', pressPlayPauseButton)
        u('#next_button').on('click', function(e){
          e.preventDefault()
          playbackRate = playbackRate * 2
        })
        u('#prev_button').on('click', function(e){
          e.preventDefault()
          playbackRate = Math.max(1, playbackRate / 2)
        })
        u('#real_time_button').on('click', function(e) {
          e.preventDefault()
          isRealTime = true
          if (resetMassStartContextMenuItem) {
            map.contextmenu.removeItem(resetMassStartContextMenuItem)
            resetMassStartContextMenuItem = null
          }
          u('#real_time_button').addClass('active')
          u('#mass_start_button').removeClass('active')
        }).text(banana.i18n('real-time'))
        u('#mass_start_button').on('click', function(e) {
          e.preventDefault()
          onPressResetMassStart()
        }).text(banana.i18n('mass-start'))
        u('#chat_show_button').on('click', displayChat)
        u('#options_show_button').on('click', displayOptions)
        u('#full_progress_bar').on('click', pressProgressBar)
        u('#share_button').on('click', shareUrl)
        if (endEvent > now) {
          isLiveEvent = true
          if (response.event.chat_enabled) {
            u('#chat_button_group').removeClass('d-none')
            connectToChatEvents()
          }
        } else {
          clock.stopRefreshes()
        }
        qrUrl = response.event.shortcut
        liveUrl = response.data

        if(response.maps.length) {
          var MapLayers = {}
          for (var i=0; i < response.maps.length; i++) {
            var m = response.maps[i]
            if (m.default) {
              m.title = m.title ? u('<span/>').text(m.title).html() : '<i class="fa fa-star"></i> Main Map'
              mapHash = m.hash
              mapUrl = m.url + '?map_hash=' + mapHash
              var bounds = [
                [m.coordinates.topLeft.lat, m.coordinates.topLeft.lon],
                [m.coordinates.topRight.lat, m.coordinates.topRight.lon],
                [m.coordinates.bottomRight.lat, m.coordinates.bottomRight.lon],
                [m.coordinates.bottomLeft.lat, m.coordinates.bottomLeft.lon],
              ]
              addRasterMap(
                bounds,
                mapUrl,
                true
              )
              MapLayers[m.title] = rasterMap
            } else {
              var bounds = [
                [m.coordinates.topLeft.lat, m.coordinates.topLeft.lon],
                [m.coordinates.topRight.lat, m.coordinates.topRight.lon],
                [m.coordinates.bottomRight.lat, m.coordinates.bottomRight.lon],
                [m.coordinates.bottomLeft.lat, m.coordinates.bottomLeft.lon],
              ]
              MapLayers[m.title] = L.tileLayer.wms(wmsService+'?', {
                  layers: eventId + '/' + i,
                  bounds: bounds,
                  tileSize: 512,
                  noWrap: true,
                  format: hasWebpSupport ? 'image/webp' : 'image/png'
              })
            }
          }
          if (response.maps.length > 1) {
              L.control.layers(MapLayers, null, {collapsed: false}).addTo(map)
              map.on('baselayerchange', function(e) {
                  console.log(e)
                  map.fitBounds(e.layer.options.bounds)
              })
          }
        } else {
          zoomOnRunners = true
        }
        if (response.announcement) {
          prevNotice = response.announcement
          u('#alert-text').text(prevNotice)
          u('.page-alerts').show()
        }
        if (!setFinishLineContextMenuItem) {
          setFinishLineContextMenuItem = map.contextmenu.insertItem({
            text: banana.i18n('draw-finish-line'),
            callback: drawFinishLine
          }, 1)
        }
        onStart()
      }
    }).fail(function(){
      u('#eventLoadingModal').remove()
      swal({text: 'Something went wrong', title: 'error', type: 'error'})
    })
  })
})()
