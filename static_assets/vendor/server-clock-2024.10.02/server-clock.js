/* server_clock.js */
var ServerClock = function (opts) {
  if (!(this instanceof ServerClock)) return new ServerClock(opts);

  const defaultOptions = { url: null, interval: 300000, burstSize: 3, burstInterval: 0.5 };
  const options = { ...defaultOptions, ...opts };
  let drifts = [];
  let refreshTimeout = null;

  function getAverageDrift() {
    let total_drift = 0;
    for (var i = 0; i < drifts.length; i++) {
      total_drift += drifts[i];
    }
    return Math.round(total_drift / (drifts.length || 1));
  }

  function onServerResponse(requestTime) {
    return function (response) {
      const now = +new Date();
      const serverTime = response.time * 1e3;
      const drift = serverTime - (now + requestTime) / 2;
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
          const clientRequestTime = +new Date();
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
