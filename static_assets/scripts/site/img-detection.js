function hasImgCookie() {
  let name = "accept-image=";
  let decodedCookie = decodeURIComponent(document.cookie);
  let ca = decodedCookie.split(";");
  for (let i = 0; i < ca.length; i++) {
    let c = ca[i];
    while (c.charAt(0) == " ") {
      c = c.substring(1);
    }
    if (c.indexOf(name) == 0) {
      return true;
    }
  }
  return false;
}
(function (document) {
  if (hasImgCookie()) {
    return;
  }
  var accepted = [];
  var formatTested = 0;
  var setFormat = function (height, format) {
    formatTested++;
    if (height == 2) {
      accepted.push("image/" + format);
    }
    if (formatTested === 3) {
      var domain = document.domain.match(/[^\.]*\.[^.]*$/)[0] + ";";
      document.cookie =
        "accept-image=" + accepted.join(",") + ";path=/;domain=." + domain;
    }
  };
  var JXL = new Image();
  JXL.onload = JXL.onerror = function () {
    setFormat(JXL.height, "jxl");
  };
  JXL.src =
    "data:image/jxl;base64,/woIAAAMABKIAgC4AF3lEgAAFSqjjBu8nOv58kOHxbSN6wxttW1hSaLIODZJJ3BIEkkaoCUzGM6qJAE=";

  var AVIF = new Image();
  AVIF.onload = AVIF.onerror = function () {
    setFormat(AVIF.height, "avif");
  };
  AVIF.src =
    "data:image/avif;base64,AAAAIGZ0eXBhdmlmAAAAAGF2aWZtaWYxbWlhZk1BMUIAAADybWV0YQAAAAAAAAAoaGRscgAAAAAAAAAAcGljdAAAAAAAAAAAAAAAAGxpYmF2aWYAAAAADnBpdG0AAAAAAAEAAAAeaWxvYwAAAABEAAABAAEAAAABAAABGgAAAB0AAAAoaWluZgAAAAAAAQAAABppbmZlAgAAAAABAABhdjAxQ29sb3IAAAAAamlwcnAAAABLaXBjbwAAABRpc3BlAAAAAAAAAAIAAAACAAAAEHBpeGkAAAAAAwgICAAAAAxhdjFDgQ0MAAAAABNjb2xybmNseAACAAIAAYAAAAAXaXBtYQAAAAAAAAABAAEEAQKDBAAAACVtZGF0EgAKCBgANogQEAwgMg8f8D///8WfhwB8+ErK42A=";

  var WebP = new Image();
  WebP.onload = WebP.onerror = function () {
    setFormat(WebP.height, "webp");
  };
  WebP.src =
    "data:image/webp;base64,UklGRjoAAABXRUJQVlA4IC4AAACyAgCdASoCAAIALmk0mk0iIiIiIgBoSygABc6WWgAA/veff/0PP8bA//LwYAAA";
})(
  (window.sandboxApi &&
    window.sandboxApi.parentWindow &&
    window.sandboxApi.parentWindow.document) ||
    document
);
