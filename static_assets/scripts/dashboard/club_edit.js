(() => {
	u("#id_slug").parent().find(".form-label").text("Domain Prefix");

	const currentLogo = u("#id_logo").parent().find("div div a").attr("href");
	if (currentLogo) {
		u("#id_logo")
			.parent()
			.find("div div a")
			.html(
				`<br/><img alt="Current Logo" height="50" width="50" src="${window.local.clubNiceUrl}logo"/>`,
			);
	}

	const currentBanner = u("#id_banner").parent().find("div div a").attr("href");
	if (currentBanner) {
		u("#id_banner")
			.parent()
			.find("div div a")
			.html(
				`<br/><img alt="Current Banner" height="210" width="400" style="aspect-ratio: 21/40; max-width: 100%;" src="${window.local.clubNiceUrl}banner"/>`,
			);
	}

	const newSlug = u("#id_name").val() === "";
	let slugEdited = false;
	u("#id_name").on("keyup", (e) => {
		if (!slugEdited) {
			const value = e.target.value;
			const slug = slugify(value, {
				strict: true,
				replacement: "-",
				trim: true,
			});
			u("#id_slug").val(slug.toLowerCase());
		}
	});

	u("#id_slug").on("blur", (e) => {
		slugEdited = e.target.value !== "";
	});

	if (newSlug) {
		u("#id_slug").val("");
	} else {
		slugEdited = true;
	}

	const newAdminsBlock = u("<div>");
	newAdminsBlock.append(
		u("#id_admins option[selected]").map((el) => {
			const name = el.textContent;
			const d = u(
				'<div class="d-inline-block me-1 mb-1 btn btn-sm btn-secondary admin-user-div">',
			);
			d.append(u('<i class="fa fa-user me-1"></i>'));
			d.append(u("<span>").text(name));

			removeElFromAdmin = () => {
				const nbAdmins = u(".admin-user-div").nodes.length;
				if (nbAdmins <= 1) {
					swal({
						title: "Error",
						text: "You must have at least one administrator listed.",
						type: "error",
					});
					return;
				}
				swal(
					{
						title: "Confirm",
						text: `You are about to remove user "${name}" from the club's administrator list.`,
						type: "warning",
						confirmButtonText: "Continue",
						showCancelButton: true,
						confirmButtonClass: "btn-danger",
					},
					(isConfirmed) => {
						if (isConfirmed) {
							el.selected = false;
							d.remove();
						}
					},
				);
			};
			d.append(
				u(
					'<button type="button" class="btn btn-close ms-1 btn-sm remove-admin-btn" aria-label="Remove admin"></button>',
				).on("click", removeElFromAdmin),
			);
			return d;
		}),
	);
	u("#id_admins").hide();
	u("#id_admins").after(newAdminsBlock);

	const inviteBtn = u("#invite-btn").clone();
	u("#invite-btn").remove();
	if (inviteBtn && u(".admin-user-div").nodes.length < 10) {
		u("#id_admins").parent().after(inviteBtn);
	}
	const submitForm = u("#change_form");
	if (submitForm) {
		submitForm.on("submit", function confirmResetStats(e) {
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
					(isConfirmed) => {
						if (isConfirmed) {
							u(e.target).off("submit");
							e.target.submit();
						} else {
							u("#id_slug").val(window.local.clubSlug);
						}
					},
				);
			}
		});
	}
	makeTextAreasAutoGrow();
})();
