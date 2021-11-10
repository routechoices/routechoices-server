if (!navigator.canShare) {
  $('#share_buttons').hide()
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
    title: $('meta[property="og:title"]').attr('content'),
    text: $('meta[property="og:description"]').attr('content'),
    url: window.location
  }
  try {
    navigator.share(shareData).then(function () {}).catch(function () {})
  } catch(err) {
  }
}

$(function() {
  $('.page-alerts').hide()
  $('.page-alert .close').on('click', function(e) {
    e.preventDefault()
    $(this).closest('.page-alert').slideUp()
  })

  $('#runners_show_button').on('click', function(e){
    e.preventDefault()
    if($('#sidebar').hasClass('d-none')){
      $('#sidebar').removeClass('d-none').addClass('col-12')
      $('#map').addClass('d-none').removeClass('col-12')
    }else if(!chatDisplayed){
      $('#sidebar').addClass('d-none').removeClass('col-12')
      $('#map').removeClass('d-none').addClass('col-12')
      map.invalidateSize()
    }
    displayCompetitorList(true)
  })

  $('#live_button').on('click', selectLiveMode)
  $('#replay_button').on('click', selectReplayMode)
  $('#play_pause_button').on('click', pressPlayPauseButton)
  $('#next_button').on('click', function(e){
    e.preventDefault()
    playbackRate = playbackRate * 2
  })
  $('#prev_button').on('click', function(e){
    e.preventDefault()
    playbackRate = Math.max(1, playbackRate/2)
  })
  $('#real_time_button').on('click', function(e) {
    e.preventDefault()
    isRealTime = true
    if (resetMassStartContextMenuItem) {
      map.contextmenu.removeItem(resetMassStartContextMenuItem)
      resetMassStartContextMenuItem = null
    }
    $('#real_time_button').addClass('active')
    $('#mass_start_button').removeClass('active')
  })
  $('#mass_start_button').on('click', function(e) {
    e.preventDefault()
    onPressResetMassStart()
  })

  $('#chat_show_button').on('click', displayChat)
  $('#options_show_button').on('click', displayOptions)
  $('#full_progress_bar').on('click', pressProgressBar)
  $('#share_button').on('click', shareUrl)

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

  $('.date-utc').each(function(i, el){
    $el = $(el)
    $el.text(dayjs($el.data('date')).local().format('MMMM D, YYYY [at] HH:mm:ss'))
  })

  map = L.map('map', {
    center: [15, 0],
    maxZoom: 17,
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
        text: 'Center map here',
        callback: centerMap
      }, '-', {
        text: 'Zoom in',
        callback: zoomIn
      }, {
        text: 'Zoom out',
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
      $('#eventLoadingModal').remove()
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
      if (endEvent > now) {
        isLiveEvent = true
        if (response.event.chat_enabled) {
          $('#chat_button_group').removeClass('d-none')
          $.ajax({
            url: 'https:'+ chatMessagesEndpoint,
            dataType: 'JSON'
          }).success(function(data){
            chatMessages = data
          })
          connectChat()
        }
      }
      qrUrl = response.event.shortcut
      liveUrl = response.data

      if(response.maps.length) {
        var MapLayers = {}
        for (var i=0; i < response.maps.length; i++) {
          var m = response.maps[i]
          if (m.default) {
            m.title = m.title ? $('<span/>').text(m.title).html() : '<i class="fa fa-star"></i> Main Map'
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
        $('#alert-text').text(prevNotice)
        $('.page-alert').slideUp(0)
        $('.page-alerts').show()
        $('.page-alert').slideDown()
      }
      if (!setFinishLineContextMenuItem) {
        setFinishLineContextMenuItem = map.contextmenu.insertItem({
          text: 'Draw finish line',
          callback: drawFinishLine
        }, 1)
      }
      onStart()
    }
  }).fail(function(){
    $('#eventLoadingModal').remove()
    swal({text: 'Something went wrong', title: 'error', type: 'error'})
  })
})