if (window.Sentry) {
  Sentry.init({
    dsn: "https://90a1a7dd37134928b5a981eeb3a20293@o91052.ingest.sentry.io/198396",
    release: "routechoices@" + window.local.siteVersion,
  });
}

function getStoredTheme() {
  let name = "theme=";
  let decodedCookie = decodeURIComponent(document.cookie);
  let ca = decodedCookie.split(";");
  for (let i = 0; i < ca.length; i++) {
    let c = ca[i];
    while (c.charAt(0) == " ") {
      c = c.substring(1);
    }
    if (c.indexOf(name) == 0) {
      return c.substring(name.length, c.length);
    }
  }
  return null;
}
const setStoredTheme = (theme) => {
  var domain = document.domain.match(/[^\.]*\.[^.]*$/)[0] + ";";
  document.cookie = "theme=" + theme + ";path=/;domain=." + domain;
};

const getPreferredTheme = () => {
  const storedTheme = getStoredTheme();
  if (storedTheme && ["light", "dark", "auto"].includes(storedTheme)) {
    return storedTheme;
  }
  return "auto";
};

const getCurrentTheme = () => {
  var theme = getPreferredTheme();
  if (
    theme === "dark" ||
    (theme === "auto" &&
      window.matchMedia("(prefers-color-scheme: dark)").matches)
  ) {
    return "dark";
  } else {
    return "light";
  }
};

const setTheme = (theme) => {
  if (
    theme === "dark" ||
    (theme === "auto" &&
      window.matchMedia("(prefers-color-scheme: dark)").matches)
  ) {
    document
      .querySelectorAll("[data-bs-theme]")
      .forEach((el) => el.setAttribute("data-bs-theme", "dark"));
  } else {
    document
      .querySelectorAll("[data-bs-theme]")
      .forEach((el) => el.setAttribute("data-bs-theme", "light"));
  }
};

(() => {
  "use strict";
  setTheme(getPreferredTheme());

  window
    .matchMedia("(prefers-color-scheme: dark)")
    .addEventListener("change", () => {
      setTheme(getPreferredTheme());
    });

  const showActiveTheme = (theme) => {
    const svgOfActiveBtn = document.querySelector(".theme-selector-icon use");
    let tooltips = {
      auto: "Auto brightness",
      dark: "Dark mode",
      light: "Bright Mode",
    };
    let icons = {
      auto: "auto",
      dark: "moon",
      light: "sun",
    };
    document
      .querySelector(".theme-selector")
      ?.setAttribute("title", tooltips[theme]);
    document
      .querySelector(".theme-selector")
      ?.setAttribute("data-bs-original-title", tooltips[theme]);
    document
      .querySelector(".theme-selector")
      ?.setAttribute("aria-label", tooltips[theme]);
    svgOfActiveBtn?.setAttribute("xlink:href", `#icon-${icons[theme]}`);
  };

  window.addEventListener("DOMContentLoaded", () => {
    showActiveTheme(getPreferredTheme());
    document.querySelectorAll(".theme-selector").forEach((toggle) => {
      new bootstrap.Tooltip(toggle, { customClass: "navbarTooltip" });
      toggle.addEventListener("click", () => {
        bootstrap.Tooltip.getInstance(".theme-selector").hide();
        let theme = getPreferredTheme();
        if (theme === "auto") {
          theme = "dark";
        } else if (theme === "dark") {
          theme = "light";
        } else {
          theme = "auto";
        }
        setStoredTheme(theme);
        setTheme(theme);
        showActiveTheme(theme);
      });
    });
  });
})();

if (needFlagsEmojiPolyfill) {
  document.body.classList.add("flags-polyfill");
}

async function checkVersion() {
  try {
    var resp = await fetch(`${window.local.apiRoot}version`).then((r) =>
      r.json()
    );
    if (resp.v !== window.local.siteVersion) {
      window.local.siteVersion = resp.v;
      console.log("New Version Available! " + resp.v);
      /*
      var alertEl = document.createElement("div");
      alertEl.classList.add(
        "alert",
        "alert-info",
        "alert-dismissible",
        "fade",
        "show"
      );
      alertEl.innerHTML =
        'A new version of Routechoices.com is available! Refresh the page to load.</button><button aria-label="Close" class="btn-close" data-bs-dismiss="alert" type="button"></button>';
      document.getElementById("django-messages").appendChild(alertEl);
      */
    }
  } catch {}
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
