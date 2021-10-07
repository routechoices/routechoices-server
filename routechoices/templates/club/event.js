{% load hosts %}
var eventId = '{{event.aid}}'
var eventUrl = "{% host_url 'event_detail' event_id=event.aid host 'api' %}"
var wmsService = "{% host_url 'wms_service' host 'api' %}"
var chatServer = '{{ chat_server }}'
var chatMessagesEndpoint = "{% host_url 'event_chat' event_id=event.aid host 'api' %}"
var clock = ServerClock({url: "{% host_url 'time_api' host 'api' %}"})