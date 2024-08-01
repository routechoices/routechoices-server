/* server_clock.js */
var ServerClock = function (opts) {
  if (!(this instanceof ServerClock)) return new ServerClock(opts);

  var defaultOptions = { url: null, interval: 300000, burstSize: 3, burstInterval: 0.5 },
    options = { ...defaultOptions, ...opts },
    drifts = [],
    refreshTimeout = null;

  function getAverageDrift() {
    var total_drift = 0;
    for (var i = 0; i < drifts.length; i++) {
      total_drift += drifts[i];
    }
    return Math.round(total_drift / (drifts.length || 1));
  }

  function onServerResponse(requestTime) {
    return function (response) {
      var now = +new Date(),
        serverTime = response.time * 1e3,
        drift = serverTime - (now + requestTime) / 2;
      drifts.push(drift);
    };
  }

  this.stopRefreshes = function () {
    if (refreshTimeout) {
      clearTimeout(refreshTimeout);
      refreshTimeout = null;
    }
  };

  this.startRefreshes = function () {
    if (refreshTimeout) return;
    (function syncClock() {
      refreshTimeout = setTimeout(syncClock, options.interval); // Every 5 minutes
      drifts = [];
      (function fetchServerTime() {
        if (drifts.length < options.burstSize) {
          var clientRequestTime = +new Date();
          fetch(options.url, {
            method: "POST",
            mode: "cors",
            headers: {
              Accept: "application/json",
            },
          })
            .then(function (r) {
              return r.json();
            })
            .then(function(r) {
              onServerResponse(clientRequestTime)(r)
              setTimeout(fetchServerTime, options.burstInterval); // Every 0.05 seconds)
            })
            .catch(function () {});
        }
      })();
    })();
  };

  if (options.url) {
    this.startRefreshes();
  }

  this.now = function () {
    return new Date(+new Date() + getAverageDrift());
  };

  this.getDrift = getAverageDrift;
};
