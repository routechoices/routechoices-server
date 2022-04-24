/* server_clock.js */
var ServerClock = function (opts) {
  if (!(this instanceof ServerClock)) return new ServerClock(opts);

  var defaultOptions = { url: null },
    options = { ...defaultOptions, ...opts },
    drifts = [],
    refreshTimeout;

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
      refreshTimeout = setTimeout(syncClock, 3 * 1e5); // Every 5 minutes
      drifts = [];
      (function fetchServerTime() {
        if (drifts.length < 3) {
          setTimeout(fetchServerTime, 500); // Every 0.5 seconds
          var clientRequestTime = +new Date();
          fetch(options.url, {
            method: "GET",
            mode: "cors",
            headers: {
              Accept: "application/json",
            },
          })
            .then(function (r) {
              return r.json();
            })
            .then(onServerResponse(clientRequestTime))
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
