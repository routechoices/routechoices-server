(function () {
  var newSlug = u("#id_name").val() == "";
  var slugEdited = false;
  if (newSlug) {
    u("#id_slug")
      .on("blur", function (e) {
        slugEdited = true;
      })
      .val("");
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
  if (submitForm && window.local.clubHasAnalytics) {
    submitForm.addEventListener("submit", function confirmResetStats(e) {
      if (
        window.local.clubSlug &&
        u("#id_slug").val() !== window.local.clubSlug
      ) {
        e.preventDefault();
        swal(
          {
            title: "Confirm",
            text: "If you proceed to change your club slug, you will loose your pages visits statistics history",
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
