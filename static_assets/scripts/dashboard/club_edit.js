(function () {
  u("#id_slug").parent().find(".form-label").text("Domain Prefix");

  var newSlug = u("#id_name").val() == "";
  var slugEdited = false;
  u("#id_name").on("keyup", function (e) {
    if (!slugEdited) {
      var value = e.target.value;
      var slug = slugify(value, {
        strict: true,
        replacement: "-",
        trim: true,
      });
      u("#id_slug").val(slug.toLowerCase());
    }
  });

  u("#id_slug").on("blur", function (e) {
    slugEdited = e.target.value !== "";
  });

  if (newSlug) {
    u("#id_slug").val("");
  } else {
    slugEdited = true;
  }

  new TomSelect("#id_admins", {
    valueField: "id",
    labelField: "username",
    searchField: "username",
    multiple: true,
    plugins: ["preserve_on_blur"],
    load: function (query, callback) {
      if (!query.length || query.length < 2) return callback();
      reqwest({
        url:
          window.local.apiBaseUrl +
          "search/user?q=" +
          encodeURIComponent(query),
        method: "get",
        type: "json",
        withCredentials: true,
        crossOrigin: true,
        success: function (res) {
          callback(res.results);
        },
        error: function () {
          callback();
        },
      });
    },
  });

  var inviteBtn = u("#invite-btn").clone();
  u("#invite-btn").remove();
  if (inviteBtn) {
    u("#id_admins-ts-label").parent().after(inviteBtn);
  }
  var submitForm = document.getElementById("change_form");
  if (submitForm) {
    submitForm.addEventListener("submit", function confirmResetStats(e) {
      if (
        window.local.clubSlug &&
        u("#id_slug").val() !== window.local.clubSlug
      ) {
        e.preventDefault();
        swal(
          {
            title: "Confirm",
            text: "You may change your domain prefix only once every 72hours.\nYour pages will still be accessible at the old domain during those 72hours.",
            type: "warning",
            confirmButtonText: "Continue",
            showCancelButton: true,
            confirmButtonClass: "btn-danger",
          },
          function (isConfirmed) {
            if (isConfirmed) {
              submitForm.removeEventListener("submit", confirmResetStats);
              submitForm.submit();
            } else {
              u("#id_slug").val(window.local.clubSlug);
            }
          }
        );
      }
    });
  }
})();
