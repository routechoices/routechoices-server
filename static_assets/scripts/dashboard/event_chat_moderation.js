var dataset = document.currentScript.dataset
var chatStreamUrl = dataset.chatStreamUrl
var chatMessagesEndpoint = dataset.chatMessagesEndpoint
var chatMessages = []

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
    refreshMessageList()
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
      chatMessages = chatMessages.filter(function(msg) {return msg.uuid !== message.uuid})
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

function refreshMessageList() {
  $('#messages').html('')
  if(!chatEventSource){
    out = '<div><i class="fa fa-spinner fa-spin fa-2x"></i> Reconnecting to server...</div>'
    $('#messages').html(out)
    return
  }
  chatMessages.sort((a, b) => b.timestamp - a.timestamp)
  chatMessages.forEach(function(msg){
    $('#messages').append('<hr/><div><span>' + hashAvatar(msg.user_hash, 20) + ' <b>'+$('<span/>').text(msg.nickname).html()+'</b></span>: '+ $('<span/>').text(msg.message).html()+ '<button class="btn btn-danger btn-sm float-end remove-msg-btn" data-msg-id="' + msg.uuid + '">Remove</button></div>')
  })
  $('#messages').append('<hr/>')
  $('#messages').find('.remove-msg-btn').on('click', function(ev){
    var uuid = ev.target.dataset.msgId
    swal({
        title: 'Confirm',
        text: 'Are you sure you want to remove this message?',
        type: 'warning',
        confirmButtonText: 'Remove',
        showCancelButton: true,
        confirmButtonClass: "btn-danger",
      },
      function(isConfirmed){
        if(isConfirmed){
          $.ajax({
            url: 'https:'+ chatMessagesEndpoint,
            data: {
              uuid: uuid
            },
            xhrFields: {
              withCredentials: true
            },
            method: 'DELETE',
            dataType: 'JSON',
            crossDomain: true
          })
        }
      }
    )
  })
}

$(function() {
  $("#messages").html('<i class="fa fa-spinner fa-spin fa-2x"></i> Connecting to chat server...')
  connectToChatEvents()
})
