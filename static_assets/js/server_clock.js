/* server_clock.js */
var ServerClock = function(opts) {
  if (!(this instanceof ServerClock)) return new ServerClock(opts);

  var defaultOptions = { url: null },
      options = $.extend({}, defaultOptions, opts),
      drifts = [];

  function getAverageDrift() {
    var total_drift = 0;
    for (var ii = 0; ii < drifts.length; ii++) {
        total_drift += drifts[ii];
    }
    if (drifts.length === 0) {
      return 0;
    } else {
      return total_drift/drifts.length;
    }
  }

  function onServerResponse(requestTime) {
    return function(response) {
      var now = +new Date(),
          serverTime = response.time * 1e3,
          drift = serverTime - (now + requestTime) / 2;
      drifts.push(drift);
    };
  }

  if(options.url) {
    (function syncClock() {
      setTimeout(syncClock, 3*1e5);    // Every 5 minutes
      drifts = [];
      (function fetchServerTime() {
        if (drifts.length < 3) {
          setTimeout(fetchServerTime, 500);    // Every 0.5 seconds
          var clientRequestTime = +new Date();
          $.ajax({
            type: 'GET',
            url: options.url,
            dataType: 'json'
          })
          .done(onServerResponse(clientRequestTime));
        }
      })();
    })();
  }

  this.now = function(){
    return new Date(+new Date() + getAverageDrift());
  };

  this.getDrift = function(){
    return getAverageDrift();
  };
};
