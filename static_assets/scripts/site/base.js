if (window.Sentry) {
  Sentry.init({
    dsn: "https://6b0a0b9b04b5a2912cda9bd502e114bb@o4507089008197632.ingest.de.sentry.io/4507247483551824",
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

const getAbsTheme = (theme) => {
  if (theme === "auto") {
    return window.matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "light";
  } else {
    return theme;
  }
};

const getCurrentTheme = () => {
  var theme = getPreferredTheme();
  return getAbsTheme(theme);
};

const setTheme = (theme) => {
  var detectedTheme = getAbsTheme(theme);
  document
    .querySelectorAll("[data-bs-theme]")
    .forEach((el) => el.setAttribute("data-bs-theme", detectedTheme));
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
