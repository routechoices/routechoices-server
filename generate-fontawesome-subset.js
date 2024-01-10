// npm install --save-dev fontawesome-subset
// npm install --save-dev @fortawesome/fontawesome-free
// npm install --save-dev sass
const fs = require("fs");
const { fontawesomeSubset } = require("fontawesome-subset");
const sass = require("sass");

fontawesomeSubset(
  {
    brands: ["twitter", "instagram", "github", "android", "apple"],
    regular: ["window-restore", "map", "copy", "clock", "eye", "eye-slash"],
    solid: [
      "arrows-rotate",
      "trash-can",
      "triangle-exclamation",
      "download",
      "arrow-up-right-from-square",
      "backward",
      "play",
      "forward",
      "users",
      "gear",
      "share-nodes",
      "house-chimney",
      "compass",
      "user",
      "envelope",
      "key",
      "shield-halved",
      "circle-plus",
      "arrow-right-arrow-left",
      "house-flag",
      "mobile-screen-button",
      "folder-open",
      "trophy",
      "link",
      "chart-pie",
      "user-plus",
      "pen-to-square",
      "stopwatch",
      "map-location-dot",
      "battery-empty",
      "battery-quarter",
      "battery-half",
      "battery-three-quarters",
      "battery-full",
      "xmark",
      "magnifying-glass",
      "right-to-bracket",
      "floppy-disk",
      "bolt",
      "upload",
      "print",
      "user-secret",
      "ban",
      "circle-check",
      "circle-xmark",
      "circle-user",
      "screwdriver-wrench",
      "circle-arrow-left",
      "image",
      "bars",
      "person-running",
      "satellite-dish",
      "star",
      "circle",
      "location-dot",
      "crosshairs",
      "highlighter",
      "eye",
      "eye-slash",
      "language",
      "pause",
      "shuffle",
      "clock",
      "arrow-down",
      "arrow-up",
      "calendar-days",
      "chevron-left",
      "chevron-right",
      "calendar-check",
      "thumbs-up",
      "file-arrow-up",
      "tag",
      "table-columns",
      "arrow-right-from-bracket",
      "pencil",
      "spinner",
      "paper-plane",
      "box-archive",
      "bell",
      "hand",
    ],
  },
  "static_assets/vendor/fontawesome-free-6.4.0-web/webfonts"
);

var a = sass.compile(
  "static_assets/vendor/fontawesome-free-6.4.0-web/scss/fontawesome.scss"
).css;
var b = sass.compile(
  "static_assets/vendor/fontawesome-free-6.4.0-web/scss/solid.scss"
).css;
var c = sass.compile(
  "static_assets/vendor/fontawesome-free-6.4.0-web/scss/regular.scss"
).css;
var d = sass.compile(
  "static_assets/vendor/fontawesome-free-6.4.0-web/scss/brands.scss"
).css;
fs.writeFileSync(
  "static_assets/vendor/fontawesome-free-6.4.0-web/css/all.css",
  [a, b, c, d].join("\n")
);
