if (window.Sentry) {
  Sentry.init({
    dsn: "https://90a1a7dd37134928b5a981eeb3a20293@o91052.ingest.sentry.io/198396",
    release: "routechoices@" + window.local.siteVersion,
  });
}

if (needFlagsEmojiPolyfill) {
  document.body.classList.add("flags-polyfill");
}

async function checkVersion() {
  var resp = await fetch(`${window.local.apiRoot}/version`).then((r) =>
    r.json()
  );
  if (resp.v !== window.local.siteVersion) {
    window.local.siteVersion = resp.v;
    console.log("New Version Available!");
  }
}
setInterval(checkVersion, 20e3);
checkVersion();

console.log(`
____________________________
|                _____     |
|              / ____  \\   |
|             / /  _ \\  \\  |
|    _____   | |  //  | |  |
|  / ____  \\  \\ \\//_ / /   |
| / /  _ \\  \\  \\  ___ /    |
|| |  //  | |  //  _____   |
| \\ \\//_ / /  // / ____  \\ |
|  \\  ___ /  // / /  _ \\  \\|
|  //       // | |  //  | ||
| //       //   \\ \\//_ / / |
|//       //     \\  ___ /  |
|/       //      //        |
|       //      //         |
|__________________________|

ROUTECHOICES.COM
Version: ${window.local.siteVersion}`);
